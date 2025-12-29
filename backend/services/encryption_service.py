"""
Encryption Service
Dịch vụ mã hóa/giải mã dữ liệu nhạy cảm sử dụng Fernet (symmetric encryption)
"""
import os
import base64
import logging
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service để mã hóa và giải mã dữ liệu nhạy cảm
    
    Sử dụng Fernet (symmetric encryption) với key được derive từ password
    hoặc từ environment variable ENCRYPTION_KEY
    """
    
    _instance: Optional['EncryptionService'] = None
    _cipher_suite: Optional[Fernet] = None
    
    def __new__(cls):
        """Singleton pattern để đảm bảo chỉ có 1 instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Khởi tạo cipher suite từ encryption key"""
        try:
            # Lấy encryption key từ environment variable
            encryption_key = os.getenv("ENCRYPTION_KEY")
            
            if not encryption_key:
                # Nếu không có key, generate một key mới và log warning
                logger.warning(
                    "ENCRYPTION_KEY not set. Generating a new key. "
                    "IMPORTANT: Set ENCRYPTION_KEY in .env file for production!"
                )
                # Generate key mới (chỉ dùng cho development)
                encryption_key = Fernet.generate_key().decode()
                logger.warning(f"Generated encryption key: {encryption_key}")
                logger.warning("Add this to your .env file: ENCRYPTION_KEY=" + encryption_key)
            
            # Nếu key là string, convert sang bytes
            if isinstance(encryption_key, str):
                # Nếu key đã là base64-encoded Fernet key, dùng trực tiếp
                if len(encryption_key) == 44 and encryption_key.endswith('='):
                    key_bytes = encryption_key.encode()
                else:
                    # Nếu là password, derive key từ password
                    key_bytes = self._derive_key_from_password(encryption_key)
            else:
                key_bytes = encryption_key
            
            # Tạo Fernet cipher suite
            self._cipher_suite = Fernet(key_bytes)
            logger.info("Encryption service initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing encryption service: {e}")
            raise
    
    @staticmethod
    def _derive_key_from_password(password: str, salt: Optional[bytes] = None) -> bytes:
        """
        Derive Fernet key từ password sử dụng PBKDF2
        
        Args:
            password: Password để derive key
            salt: Salt (nếu None, sẽ dùng default salt từ ENCRYPTION_SALT env var)
        
        Returns:
            Fernet key (32 bytes, base64-encoded)
        """
        if salt is None:
            # Lấy salt từ environment hoặc dùng default
            salt_str = os.getenv("ENCRYPTION_SALT", "default_salt_change_in_production")
            salt = salt_str.encode()
        
        # Derive key từ password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate một Fernet key mới
        
        Returns:
            Base64-encoded Fernet key (string)
        """
        return Fernet.generate_key().decode()
    
    def encrypt(self, plaintext: str) -> str:
        """
        Mã hóa plaintext
        
        Args:
            plaintext: Text cần mã hóa
        
        Returns:
            Encrypted text (base64-encoded)
        
        Raises:
            ValueError: Nếu plaintext là None hoặc empty
            RuntimeError: Nếu encryption service chưa được khởi tạo
        """
        if plaintext is None:
            return None
        
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        
        if not plaintext:
            return ""
        
        if self._cipher_suite is None:
            raise RuntimeError("Encryption service not initialized")
        
        try:
            encrypted_bytes = self._cipher_suite.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Error encrypting data: {e}")
            raise
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Giải mã ciphertext
        
        Args:
            ciphertext: Encrypted text cần giải mã
        
        Returns:
            Decrypted plaintext
        
        Raises:
            ValueError: Nếu ciphertext không hợp lệ hoặc không thể giải mã
            RuntimeError: Nếu encryption service chưa được khởi tạo
        """
        if ciphertext is None:
            return None
        
        if not isinstance(ciphertext, str):
            ciphertext = str(ciphertext)
        
        if not ciphertext:
            return ""
        
        if self._cipher_suite is None:
            raise RuntimeError("Encryption service not initialized")
        
        try:
            decrypted_bytes = self._cipher_suite.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            # Nếu không thể decrypt, có thể là plaintext cũ (chưa được encrypt)
            # Trả về nguyên bản để backward compatibility
            logger.warning(f"Failed to decrypt, returning original (may be unencrypted data): {e}")
            return ciphertext
    
    def is_encrypted(self, text: str) -> bool:
        """
        Kiểm tra xem text có phải là encrypted data không
        
        Args:
            text: Text cần kiểm tra
        
        Returns:
            True nếu có vẻ là encrypted data, False nếu không
        """
        if not text:
            return False
        
        try:
            # Fernet encrypted data bắt đầu với 'gAAAA' và là base64-encoded
            # Kiểm tra format cơ bản
            if not text.startswith('gAAAA'):
                return False
            
            # Thử decode base64 để verify format
            decoded = base64.urlsafe_b64decode(text.encode())
            # Fernet token có độ dài cố định (sau khi decode)
            # Format: version (1 byte) + timestamp (8 bytes) + IV (16 bytes) + HMAC (32 bytes) + ciphertext
            return len(decoded) >= 57  # Minimum length for valid Fernet token
        except Exception:
            # Nếu không decode được, không phải encrypted data
            return False


# Singleton instance
encryption_service = EncryptionService()