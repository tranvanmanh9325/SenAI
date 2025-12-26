"""
Centralized Error Handling System for Backend

Features:
- Consistent error logging with stack traces
- User-friendly error messages
- Retry logic for external services
- Error categorization
- Structured error responses
"""

import logging
import traceback
import functools
from typing import Optional, Callable, TypeVar, Any
from enum import Enum
from fastapi import HTTPException
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorCategory(Enum):
    """Error categories for better error handling"""
    NETWORK = "network"
    DATABASE = "database"
    VALIDATION = "validation"
    LLM = "llm"
    EXTERNAL_API = "external_api"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AppError(Exception):
    """Base application error with context"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        user_message: Optional[str] = None,
        technical_details: Optional[str] = None,
        status_code: int = 500
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.user_message = user_message or self._get_default_user_message(category)
        self.technical_details = technical_details
        self.status_code = status_code
        super().__init__(self.message)
    
    def _get_default_user_message(self, category: ErrorCategory) -> str:
        """Get default user-friendly message based on category"""
        messages = {
            ErrorCategory.NETWORK: "Lỗi kết nối mạng. Vui lòng thử lại sau.",
            ErrorCategory.DATABASE: "Lỗi truy cập cơ sở dữ liệu. Vui lòng thử lại sau.",
            ErrorCategory.VALIDATION: "Dữ liệu không hợp lệ. Vui lòng kiểm tra lại.",
            ErrorCategory.LLM: "Lỗi khi xử lý yêu cầu AI. Vui lòng thử lại sau.",
            ErrorCategory.EXTERNAL_API: "Lỗi khi gọi dịch vụ bên ngoài. Vui lòng thử lại sau.",
            ErrorCategory.SYSTEM: "Đã xảy ra lỗi hệ thống. Vui lòng thử lại sau.",
            ErrorCategory.UNKNOWN: "Đã xảy ra lỗi không xác định. Vui lòng thử lại sau."
        }
        return messages.get(category, messages[ErrorCategory.UNKNOWN])
    
    def to_dict(self) -> dict:
        """Convert error to dictionary for API response"""
        return {
            "error": True,
            "message": self.user_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "technical_details": self.technical_details if self.severity == ErrorSeverity.ERROR else None
        }


def log_error(
    error: Exception,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    context: Optional[str] = None,
    include_stack_trace: bool = True
):
    """
    Log error with full context and stack trace
    
    Args:
        error: The exception to log
        category: Error category
        severity: Error severity level
        context: Additional context (function name, etc.)
        include_stack_trace: Whether to include stack trace
    """
    log_message = f"[{category.value.upper()}] [{severity.value.upper()}]"
    
    if context:
        log_message += f" [{context}]"
    
    log_message += f" {str(error)}"
    
    if include_stack_trace:
        stack_trace = traceback.format_exc()
        log_message += f"\nStack trace:\n{stack_trace}"
    
    # Log based on severity
    if severity == ErrorSeverity.CRITICAL:
        logger.critical(log_message)
    elif severity == ErrorSeverity.ERROR:
        logger.error(log_message)
    elif severity == ErrorSeverity.WARNING:
        logger.warning(log_message)
    else:
        logger.info(log_message)


def handle_error(
    error: Exception,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    context: Optional[str] = None,
    user_message: Optional[str] = None,
    status_code: int = 500,
    include_stack_trace: bool = True
) -> HTTPException:
    """
    Handle error and return HTTPException with proper logging
    
    Args:
        error: The exception to handle
        category: Error category
        severity: Error severity level
        context: Additional context
        user_message: User-friendly error message
        status_code: HTTP status code
        include_stack_trace: Whether to include stack trace in logs
    
    Returns:
        HTTPException ready to be raised
    """
    # Log the error
    log_error(error, category, severity, context, include_stack_trace)
    
    # Create user-friendly message
    if not user_message:
        if isinstance(error, AppError):
            user_message = error.user_message
        else:
            app_error = AppError(str(error), category, severity)
            user_message = app_error.user_message
    
    # Create technical details (only for errors, not warnings)
    technical_details = None
    if severity == ErrorSeverity.ERROR and include_stack_trace:
        technical_details = traceback.format_exc()
    
    # Return HTTPException
    return HTTPException(
        status_code=status_code,
        detail={
            "error": True,
            "message": user_message,
            "category": category.value,
            "severity": severity.value,
            "technical_details": technical_details
        }
    )


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    category: ErrorCategory = ErrorCategory.UNKNOWN
):
    """
    Decorator to retry operations on failure
    
    Args:
        max_retries: Maximum number of retries
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry
        category: Error category for logging
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        log_error(
                            e,
                            category=category,
                            severity=ErrorSeverity.WARNING,
                            context=f"{func.__name__} (attempt {attempt + 1}/{max_retries + 1})",
                            include_stack_trace=False
                        )
                        
                        # Wait before retrying
                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        # All retries exhausted
                        log_error(
                            e,
                            category=category,
                            severity=ErrorSeverity.ERROR,
                            context=f"{func.__name__} (all {max_retries + 1} attempts failed)",
                            include_stack_trace=True
                        )
                        raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise Exception(f"Function {func.__name__} failed after {max_retries + 1} attempts")
        
        return wrapper
    return decorator


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable
    
    Args:
        error: The exception to check
    
    Returns:
        True if error is retryable, False otherwise
    """
    error_str = str(error).lower()
    
    # Network-related errors
    retryable_patterns = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "503",  # Service Unavailable
        "502",  # Bad Gateway
        "504",  # Gateway Timeout
        "429",  # Too Many Requests
    ]
    
    return any(pattern in error_str for pattern in retryable_patterns)


def safe_execute(
    func: Callable[..., T],
    default_value: T,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    context: Optional[str] = None,
    log_error_flag: bool = True
) -> T:
    """
    Safely execute a function and return default value on error
    
    Args:
        func: Function to execute
        default_value: Value to return on error
        category: Error category
        context: Additional context
        log_error_flag: Whether to log errors
    
    Returns:
        Function result or default_value on error
    """
    try:
        return func()
    except Exception as e:
        if log_error_flag:
            log_error(e, category=category, context=context or func.__name__, include_stack_trace=True)
        return default_value


# Convenience functions for common error types
def handle_network_error(error: Exception, context: Optional[str] = None) -> HTTPException:
    """Handle network-related errors"""
    return handle_error(
        error,
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.ERROR,
        context=context,
        status_code=503
    )


def handle_database_error(error: Exception, context: Optional[str] = None) -> HTTPException:
    """Handle database-related errors"""
    return handle_error(
        error,
        category=ErrorCategory.DATABASE,
        severity=ErrorSeverity.ERROR,
        context=context,
        status_code=500
    )


def handle_validation_error(error: Exception, context: Optional[str] = None) -> HTTPException:
    """Handle validation errors"""
    return handle_error(
        error,
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.WARNING,
        context=context,
        status_code=400
    )


def handle_llm_error(error: Exception, context: Optional[str] = None) -> HTTPException:
    """Handle LLM-related errors"""
    return handle_error(
        error,
        category=ErrorCategory.LLM,
        severity=ErrorSeverity.ERROR,
        context=context,
        status_code=500
    )