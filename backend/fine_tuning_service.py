"""
Fine-tuning Service để học từ dữ liệu conversations và feedback
Hỗ trợ tạo training data và fine-tune model
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class FineTuningService:
    """Service để quản lý fine-tuning từ conversations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.training_data_dir = os.getenv("TRAINING_DATA_DIR", "./training_data")
        os.makedirs(self.training_data_dir, exist_ok=True)
    
    def export_conversations_for_training(
        self, 
        session_id: Optional[str] = None,
        min_conversations: int = 10,
        output_format: str = "jsonl"  # jsonl, json, txt
    ) -> Dict[str, Any]:
        """
        Export conversations từ database để tạo training data
        
        Args:
            session_id: Filter theo session (None = tất cả)
            min_conversations: Số lượng conversations tối thiểu
            output_format: Format output (jsonl, json, txt)
            
        Returns:
            Dict với thông tin về exported data
        """
        try:
            # Query conversations
            query = self.db.query(
                text("""
                    SELECT user_message, ai_response, session_id, created_at
                    FROM agent_conversations
                    WHERE ai_response IS NOT NULL AND ai_response != ''
                """)
            )
            
            if session_id:
                query = self.db.execute(
                    text("""
                        SELECT user_message, ai_response, session_id, created_at
                        FROM agent_conversations
                        WHERE session_id = :session_id 
                        AND ai_response IS NOT NULL AND ai_response != ''
                        ORDER BY created_at
                    """),
                    {"session_id": session_id}
                )
            else:
                query = self.db.execute(
                    text("""
                        SELECT user_message, ai_response, session_id, created_at
                        FROM agent_conversations
                        WHERE ai_response IS NOT NULL AND ai_response != ''
                        ORDER BY created_at
                    """)
                )
            
            conversations = query.fetchall()
            
            if len(conversations) < min_conversations:
                return {
                    "success": False,
                    "message": f"Cần ít nhất {min_conversations} conversations, hiện có {len(conversations)}",
                    "count": len(conversations)
                }
            
            # Convert to training format
            training_data = []
            for conv in conversations:
                training_data.append({
                    "instruction": conv[0],  # user_message
                    "input": "",
                    "output": conv[1],  # ai_response
                    "session_id": conv[2],
                    "created_at": conv[3].isoformat() if conv[3] else None
                })
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{timestamp}.{output_format}"
            filepath = os.path.join(self.training_data_dir, filename)
            
            if output_format == "jsonl":
                with open(filepath, "w", encoding="utf-8") as f:
                    for item in training_data:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
            elif output_format == "json":
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(training_data, f, ensure_ascii=False, indent=2)
            else:  # txt
                with open(filepath, "w", encoding="utf-8") as f:
                    for item in training_data:
                        f.write(f"Instruction: {item['instruction']}\n")
                        f.write(f"Output: {item['output']}\n")
                        f.write("---\n")
            
            return {
                "success": True,
                "filepath": filepath,
                "filename": filename,
                "count": len(training_data),
                "format": output_format
            }
        except Exception as e:
            logger.error(f"Error exporting conversations: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_ollama_finetune_data(
        self,
        session_id: Optional[str] = None,
        min_conversations: int = 10
    ) -> Dict[str, Any]:
        """
        Tạo training data format cho Ollama fine-tuning
        
        Ollama sử dụng format:
        {
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
        """
        try:
            query = self.db.execute(
                text("""
                    SELECT user_message, ai_response, session_id, created_at
                    FROM agent_conversations
                    WHERE ai_response IS NOT NULL AND ai_response != ''
                    ORDER BY created_at
                """)
            )
            
            conversations = query.fetchall()
            
            if len(conversations) < min_conversations:
                return {
                    "success": False,
                    "message": f"Cần ít nhất {min_conversations} conversations, hiện có {len(conversations)}",
                    "count": len(conversations)
                }
            
            # Group by session để tạo conversation flow
            training_data = []
            current_session = None
            messages = []
            
            for conv in conversations:
                user_msg, ai_resp, sess_id, created_at = conv
                
                # Nếu session thay đổi, lưu conversation cũ
                if current_session and current_session != sess_id and messages:
                    training_data.append({"messages": messages})
                    messages = []
                
                current_session = sess_id
                messages.append({"role": "user", "content": user_msg})
                messages.append({"role": "assistant", "content": ai_resp})
            
            # Lưu conversation cuối
            if messages:
                training_data.append({"messages": messages})
            
            # Save to JSONL
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ollama_finetune_{timestamp}.jsonl"
            filepath = os.path.join(self.training_data_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                for item in training_data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
            return {
                "success": True,
                "filepath": filepath,
                "filename": filename,
                "count": len(training_data),
                "format": "ollama_jsonl"
            }
        except Exception as e:
            logger.error(f"Error creating Ollama fine-tune data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Lấy thống kê về dữ liệu training"""
        try:
            # Count total conversations
            total_query = self.db.execute(
                text("SELECT COUNT(*) FROM agent_conversations WHERE ai_response IS NOT NULL")
            )
            total = total_query.scalar() or 0
            
            # Count by session
            sessions_query = self.db.execute(
                text("""
                    SELECT session_id, COUNT(*) as count
                    FROM agent_conversations
                    WHERE ai_response IS NOT NULL
                    GROUP BY session_id
                """)
            )
            sessions = sessions_query.fetchall()
            
            # Count training files
            training_files = []
            if os.path.exists(self.training_data_dir):
                training_files = [
                    f for f in os.listdir(self.training_data_dir)
                    if f.endswith(('.jsonl', '.json', '.txt'))
                ]
            
            return {
                "total_conversations": total,
                "total_sessions": len(sessions),
                "training_files_count": len(training_files),
                "training_files": training_files,
                "min_for_training": 10,
                "ready_for_training": total >= 10
            }
        except Exception as e:
            logger.error(f"Error getting training stats: {e}")
            return {
                "error": str(e)
            }
    
    def prepare_finetune_instructions(self) -> str:
        """
        Tạo hướng dẫn fine-tuning cho user
        """
        instructions = """
# Hướng dẫn Fine-tuning Llama3.1 với Ollama

## Bước 1: Thu thập Feedback
- Sử dụng API POST /api/feedback để submit feedback cho conversations
- Rating: 1-5 stars (hoặc thumbs up/down)
- User correction: Cung cấp câu trả lời đúng nếu AI trả lời sai
- Cần ít nhất 5-10 conversations với feedback tốt (rating >= 3)

## Bước 2: Export training data với feedback
API endpoint: POST /api/finetune/export?format=ollama&use_feedback=true
- Format: jsonl (cho Ollama)
- Sẽ ưu tiên sử dụng user corrections và high-rating responses

## Bước 3: Fine-tune với Ollama
```bash
# Tạo model mới từ base model
ollama create my-custom-model -f Modelfile

# Hoặc fine-tune trực tiếp
ollama create my-custom-model --from llama3.1
```

## Bước 4: Sử dụng model đã fine-tune
Cập nhật biến môi trường:
LLM_MODEL_NAME=my-custom-model

## Lưu ý:
- Fine-tuning với feedback sẽ cho kết quả tốt hơn
- User corrections được ưu tiên cao nhất
- High-rating responses được giữ lại
- Low-rating responses bị loại bỏ
- Training data format: JSONL với messages array
        """
        return instructions