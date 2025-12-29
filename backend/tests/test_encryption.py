"""
Test script để verify encryption service hoạt động đúng

Usage:
    cd backend
    venv\\Scripts\\activate  (Windows)
    source venv/bin/activate  (Linux/Mac)
    python test_encryption.py
"""
import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from services.encryption_service import encryption_service, EncryptionService

# Load environment variables
load_dotenv()


def test_encryption_basic():
    """Test basic encryption/decryption"""
    print("="*60)
    print("Test 1: Basic Encryption/Decryption")
    print("="*60)
    
    test_data = [
        "Hello, World!",
        "This is a test comment with special chars: !@#$%^&*()",
        "User correction: The answer should be...",
        "",  # Empty string
        "A" * 1000,  # Long string
    ]
    
    for i, plaintext in enumerate(test_data, 1):
        try:
            encrypted = encryption_service.encrypt(plaintext)
            decrypted = encryption_service.decrypt(encrypted)
            
            # Empty string is a special case - it's not encrypted (returns empty string)
            # This is by design since empty string doesn't contain sensitive data
            if plaintext == "":
                # For empty string: encrypted should be empty, decrypted should be empty
                # and they should match
                success = (decrypted == plaintext == encrypted == "")
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"\nTest {i}: {status}")
                print(f"  Original: (empty string)")
                print(f"  Encrypted: (empty string - not encrypted by design)")
                print(f"  Decrypted: (empty string)")
                print(f"  Note: Empty strings are not encrypted (no sensitive data)")
            else:
                is_encrypted_check = encryption_service.is_encrypted(encrypted)
                is_plaintext_check = encryption_service.is_encrypted(plaintext)
                
                success = (decrypted == plaintext) and is_encrypted_check and not is_plaintext_check
                
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"\nTest {i}: {status}")
                print(f"  Original: {plaintext[:50]}{'...' if len(plaintext) > 50 else ''}")
                print(f"  Encrypted: {encrypted[:50]}...")
                print(f"  Decrypted: {decrypted[:50]}{'...' if len(decrypted) > 50 else ''}")
                print(f"  Is encrypted check: {is_encrypted_check} (expected: True)")
                print(f"  Is plaintext check: {is_plaintext_check} (expected: False)")
            
            if not success:
                print(f"  ERROR: Encryption/decryption failed!")
                return False
                
        except Exception as e:
            print(f"\nTest {i}: ✗ FAIL")
            print(f"  ERROR: {e}")
            return False
    
    print("\n✓ All basic tests passed!")
    return True


def test_none_values():
    """Test handling None values"""
    print("\n" + "="*60)
    print("Test 2: None Value Handling")
    print("="*60)
    
    try:
        encrypted_none = encryption_service.encrypt(None)
        decrypted_none = encryption_service.decrypt(None)
        
        if encrypted_none is None and decrypted_none is None:
            print("✓ None values handled correctly")
            return True
        else:
            print(f"✗ FAIL: Expected None, got encrypted={encrypted_none}, decrypted={decrypted_none}")
            return False
    except Exception as e:
        print(f"✗ FAIL: Error handling None: {e}")
        return False


def test_key_generation():
    """Test key generation"""
    print("\n" + "="*60)
    print("Test 3: Key Generation")
    print("="*60)
    
    try:
        key1 = EncryptionService.generate_key()
        key2 = EncryptionService.generate_key()
        
        if len(key1) == 44 and len(key2) == 44 and key1 != key2:
            print(f"✓ Key generation works correctly")
            print(f"  Key 1: {key1[:20]}...")
            print(f"  Key 2: {key2[:20]}...")
            print(f"  Keys are different: {key1 != key2}")
            return True
        else:
            print(f"✗ FAIL: Invalid keys generated")
            return False
    except Exception as e:
        print(f"✗ FAIL: Error generating keys: {e}")
        return False


def test_backward_compatibility():
    """Test backward compatibility với unencrypted data"""
    print("\n" + "="*60)
    print("Test 4: Backward Compatibility")
    print("="*60)
    
    # Simulate unencrypted data (plaintext)
    unencrypted_text = "This is plaintext data"
    
    try:
        # is_encrypted should return False
        is_encrypted = encryption_service.is_encrypted(unencrypted_text)
        if not is_encrypted:
            print("✓ Unencrypted data detected correctly")
        else:
            print("✗ FAIL: Unencrypted data incorrectly identified as encrypted")
            return False
        
        # decrypt should return original if not encrypted (backward compatibility)
        decrypted = encryption_service.decrypt(unencrypted_text)
        if decrypted == unencrypted_text:
            print("✓ Backward compatibility works (decrypt returns original for unencrypted data)")
            return True
        else:
            print(f"✗ FAIL: Backward compatibility broken. Expected: {unencrypted_text}, Got: {decrypted}")
            return False
    except Exception as e:
        print(f"✗ FAIL: Error testing backward compatibility: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("ENCRYPTION SERVICE TEST SUITE")
    print("="*60)
    
    # Check if ENCRYPTION_KEY is set
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        print("\n⚠ WARNING: ENCRYPTION_KEY not set in .env")
        print("  The service will generate a new key (development mode only)")
        print("  For production, set ENCRYPTION_KEY in .env file")
        print()
    
    tests = [
        test_encryption_basic,
        test_none_values,
        test_key_generation,
        test_backward_compatibility,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())