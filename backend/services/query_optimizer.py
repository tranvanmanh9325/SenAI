"""
Query Optimization Utility
Cung cấp các công cụ để optimize và analyze database queries với EXPLAIN ANALYZE
"""
from sqlalchemy import text, Engine
from typing import Dict, Any, Optional, List
import logging
import json
import re

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Utility class để optimize và analyze database queries"""
    
    def __init__(self, engine: Engine):
        self.engine = engine
    
    def explain_analyze(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Chạy EXPLAIN ANALYZE cho query và trả về kết quả
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
        
        Returns:
            Dict chứa execution plan và statistics
        """
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) {query}"
        
        try:
            with self.engine.connect() as conn:
                if params:
                    result = conn.execute(text(explain_query), params)
                else:
                    result = conn.execute(text(explain_query))
                
                # EXPLAIN ANALYZE với FORMAT JSON trả về một row với một column chứa JSON
                row = result.fetchone()
                if row:
                    plan_json = row[0]
                    if isinstance(plan_json, str):
                        plan_data = json.loads(plan_json)
                    else:
                        plan_data = plan_json
                    
                    return self._parse_explain_result(plan_data)
                else:
                    return {"error": "No execution plan returned"}
        
        except Exception as e:
            logger.error(f"Error running EXPLAIN ANALYZE: {e}")
            return {"error": str(e)}
    
    def _parse_explain_result(self, plan_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse EXPLAIN ANALYZE result thành format dễ đọc"""
        if not plan_data or not isinstance(plan_data, list):
            return {"error": "Invalid plan data"}
        
        plan = plan_data[0].get("Plan", {})
        
        # Extract thông tin quan trọng
        result = {
            "total_cost": plan.get("Total Cost"),
            "actual_total_time": plan.get("Actual Total Time"),
            "actual_rows": plan.get("Actual Rows"),
            "planning_time": plan_data[0].get("Planning Time"),
            "execution_time": plan_data[0].get("Execution Time"),
            "buffers": plan_data[0].get("Buffers", {}),
            "plan": self._extract_plan_details(plan)
        }
        
        return result
    
    def _extract_plan_details(self, plan: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """Extract chi tiết từ execution plan"""
        details = {
            "node_type": plan.get("Node Type"),
            "relation_name": plan.get("Relation Name"),
            "alias": plan.get("Alias"),
            "startup_cost": plan.get("Startup Cost"),
            "total_cost": plan.get("Total Cost"),
            "plan_rows": plan.get("Plan Rows"),
            "plan_width": plan.get("Plan Width"),
            "actual_startup_time": plan.get("Actual Startup Time"),
            "actual_total_time": plan.get("Actual Total Time"),
            "actual_rows": plan.get("Actual Rows"),
            "actual_loops": plan.get("Actual Loops"),
            "index_name": plan.get("Index Name"),
            "index_cond": plan.get("Index Cond"),
            "filter": plan.get("Filter"),
            "join_type": plan.get("Join Type"),
            "join_filter": plan.get("Join Filter"),
            "hash_cond": plan.get("Hash Cond"),
            "sort_key": plan.get("Sort Key"),
            "sort_method": plan.get("Sort Method"),
            "sort_space_used": plan.get("Sort Space Used"),
        }
        
        # Recursively extract child plans
        if "Plans" in plan:
            details["children"] = [
                self._extract_plan_details(child, depth + 1)
                for child in plan["Plans"]
            ]
        
        return details
    
    def check_index_usage(self, query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Kiểm tra xem query có sử dụng indexes không
        
        Returns:
            Dict với thông tin về index usage
        """
        explain_result = self.explain_analyze(query, params)
        
        if "error" in explain_result:
            return explain_result
        
        # Tìm tất cả indexes được sử dụng
        indexes_used = []
        seq_scans = []
        
        def traverse_plan(plan: Dict[str, Any]):
            node_type = plan.get("node_type", "")
            
            if node_type == "Index Scan" or node_type == "Index Only Scan":
                index_name = plan.get("index_name")
                relation_name = plan.get("relation_name")
                if index_name:
                    indexes_used.append({
                        "index": index_name,
                        "table": relation_name,
                        "type": node_type
                    })
            
            if node_type == "Seq Scan":
                relation_name = plan.get("relation_name")
                if relation_name:
                    seq_scans.append({
                        "table": relation_name,
                        "rows": plan.get("actual_rows", 0)
                    })
            
            # Traverse children
            if "children" in plan:
                for child in plan["children"]:
                    traverse_plan(child)
        
        traverse_plan(explain_result.get("plan", {}))
        
        return {
            "indexes_used": indexes_used,
            "sequential_scans": seq_scans,
            "has_index_usage": len(indexes_used) > 0,
            "has_seq_scans": len(seq_scans) > 0,
            "recommendation": self._generate_recommendation(indexes_used, seq_scans, explain_result)
        }
    
    def _generate_recommendation(self, indexes_used: List[Dict], seq_scans: List[Dict],
                                explain_result: Dict[str, Any]) -> str:
        """Generate recommendation dựa trên execution plan"""
        recommendations = []
        
        if seq_scans:
            for scan in seq_scans:
                if scan["rows"] > 1000:
                    recommendations.append(
                        f"⚠️  Sequential scan trên bảng {scan['table']} với {scan['rows']} rows. "
                        f"Cân nhắc thêm index cho các columns thường được filter/sort."
                    )
        
        if not indexes_used and seq_scans:
            recommendations.append(
                "⚠️  Query không sử dụng indexes. Cân nhắc thêm indexes cho các columns "
                "thường được query."
            )
        
        execution_time = explain_result.get("execution_time", 0)
        if execution_time > 100:  # > 100ms
            recommendations.append(
                f"⚠️  Query execution time ({execution_time:.2f}ms) khá chậm. "
                f"Cân nhắc optimize query hoặc thêm indexes."
            )
        
        if not recommendations:
            return "✅ Query đã được optimize tốt!"
        
        return "\n".join(recommendations)
    
    def suggest_indexes(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Suggest indexes dựa trên query pattern
        
        Returns:
            List of suggested index creation SQL statements
        """
        suggestions = []
        
        # Parse WHERE clauses
        where_pattern = r"WHERE\s+(\w+)\s*="
        where_matches = re.findall(where_pattern, query, re.IGNORECASE)
        
        # Parse JOIN clauses
        join_pattern = r"JOIN\s+(\w+)\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)"
        join_matches = re.findall(join_pattern, query, re.IGNORECASE)
        
        # Parse ORDER BY clauses
        order_pattern = r"ORDER\s+BY\s+(\w+)(?:\s+(\w+))?"
        order_matches = re.findall(order_pattern, query, re.IGNORECASE)
        
        # Suggest indexes cho WHERE clauses
        for column in where_matches:
            suggestions.append(f"CREATE INDEX idx_{column} ON table_name({column});")
        
        # Suggest composite indexes cho JOIN + WHERE
        if join_matches and where_matches:
            for join_match in join_matches:
                table = join_match[0]
                join_col = join_match[2] if join_match[2] == join_match[4] else None
                if join_col:
                    suggestions.append(
                        f"CREATE INDEX idx_{table}_{join_col} ON {table}({join_col});"
                    )
        
        return suggestions
    
    def analyze_slow_queries(self, min_execution_time: float = 100.0) -> List[Dict[str, Any]]:
        """
        Analyze slow queries từ pg_stat_statements (nếu available)
        
        Args:
            min_execution_time: Minimum execution time in milliseconds
        
        Returns:
            List of slow queries với statistics
        """
        try:
            # Kiểm tra xem pg_stat_statements extension có được enable không
            check_ext_query = """
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                )
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(text(check_ext_query))
                if not result.scalar():
                    logger.warning("pg_stat_statements extension không được enable. "
                                 "Không thể analyze slow queries.")
                    return []
                
                # Query slow queries
                slow_queries_query = text("""
                    SELECT 
                        query,
                        calls,
                        total_exec_time,
                        mean_exec_time,
                        max_exec_time,
                        min_exec_time,
                        stddev_exec_time
                    FROM pg_stat_statements
                    WHERE mean_exec_time >= :min_time
                    ORDER BY mean_exec_time DESC
                    LIMIT 20
                """)
                
                result = conn.execute(slow_queries_query, {"min_time": min_execution_time})
                
                slow_queries = []
                for row in result:
                    slow_queries.append({
                        "query": row[0][:200] + "..." if len(row[0]) > 200 else row[0],
                        "calls": row[1],
                        "total_exec_time": float(row[2]),
                        "mean_exec_time": float(row[3]),
                        "max_exec_time": float(row[4]),
                        "min_exec_time": float(row[5]),
                        "stddev_exec_time": float(row[6]) if row[6] else None
                    })
                
                return slow_queries
        
        except Exception as e:
            logger.error(f"Error analyzing slow queries: {e}")
            return []


def get_query_optimizer(engine: Engine) -> QueryOptimizer:
    """Factory function để tạo QueryOptimizer instance"""
    return QueryOptimizer(engine)