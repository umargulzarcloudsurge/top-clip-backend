#!/usr/bin/env python3
"""
Multi-Threading Setup Verification Script
Tests all components before starting the server to ensure no issues
"""

import os
import sys
import traceback

def test_basic_imports():
    """Test all required imports"""
    print("🔍 Testing basic imports...")
    try:
        import concurrent.futures
        import multiprocessing
        import asyncio
        from datetime import datetime
        from typing import Dict, List, Optional, Any, Union
        import logging
        import json
        import uuid
        
        from fastapi import FastAPI, HTTPException
        print("✅ All basic imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_thread_pool_setup():
    """Test thread pool configuration"""
    print("🔍 Testing thread pool setup...")
    try:
        import concurrent.futures
        import multiprocessing
        
        # Detect system capabilities with safety checks (same as main.py)
        try:
            CPU_COUNT = multiprocessing.cpu_count()
            THREAD_COUNT = min(CPU_COUNT * 2, 8)
        except Exception as cpu_error:
            print(f"⚠️ Could not detect CPU count: {cpu_error}, using fallback")
            CPU_COUNT = 4  # Safe fallback
            THREAD_COUNT = 8  # Safe fallback for 4c/8t systems
        
        print(f"💻 System detected: {CPU_COUNT} cores, using {THREAD_COUNT} threads")
        
        # Create thread pools (same as main.py)
        video_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=THREAD_COUNT,
            thread_name_prefix="video_processing"
        )
        
        io_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="io_operations"
        )
        
        face_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(2, CPU_COUNT // 2),
            thread_name_prefix="face_detection"
        )
        
        print(f"✅ Video executor: {THREAD_COUNT} threads")
        print(f"✅ I/O executor: 4 threads") 
        print(f"✅ Face executor: {max(2, CPU_COUNT // 2)} threads")
        
        # Test thread pool functionality
        def test_task(x):
            return x * 2
        
        # Submit test tasks
        futures = []
        for i in range(5):
            future = video_executor.submit(test_task, i)
            futures.append(future)
        
        # Get results
        results = [future.result() for future in futures]
        expected = [0, 2, 4, 6, 8]
        
        if results == expected:
            print("✅ Thread pool functionality test passed")
        else:
            print(f"❌ Thread pool test failed: expected {expected}, got {results}")
            return False
        
        # Shutdown executors
        video_executor.shutdown()
        io_executor.shutdown()
        face_executor.shutdown()
        print("✅ Thread pool cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Thread pool setup error: {e}")
        traceback.print_exc()
        return False

def test_enhanced_video_service():
    """Test Enhanced Video Service import and method existence"""
    print("🔍 Testing Enhanced Video Service...")
    try:
        # Add the Backend-main directory to sys.path
        backend_path = os.path.dirname(os.path.abspath(__file__))
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        
        from utils.enhanced_video_service import EnhancedVideoService
        
        # Create instance
        service = EnhancedVideoService()
        
        # Check if required methods exist
        if hasattr(service, 'process_video_with_captions'):
            print("✅ process_video_with_captions method exists")
        else:
            print("❌ process_video_with_captions method missing")
            return False
            
        if hasattr(service, 'process_video_with_captions_parallel'):
            print("✅ process_video_with_captions_parallel method exists")
        else:
            print("❌ process_video_with_captions_parallel method missing")
            return False
        
        print("✅ Enhanced Video Service import and setup successful")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced Video Service error: {e}")
        traceback.print_exc()
        return False

def test_async_functionality():
    """Test async functionality"""
    print("🔍 Testing async functionality...")
    try:
        import asyncio
        
        async def test_async_task():
            await asyncio.sleep(0.1)
            return "async success"
        
        # Test async execution
        result = asyncio.run(test_async_task())
        
        if result == "async success":
            print("✅ Async functionality test passed")
            return True
        else:
            print(f"❌ Async test failed: got {result}")
            return False
            
    except Exception as e:
        print(f"❌ Async functionality error: {e}")
        traceback.print_exc()
        return False

def test_logging_setup():
    """Test logging configuration"""
    print("🔍 Testing logging setup...")
    try:
        import logging
        
        # Test logger creation
        logger = logging.getLogger("test_logger")
        logger.info("Test log message")
        
        print("✅ Logging setup successful")
        return True
        
    except Exception as e:
        print(f"❌ Logging setup error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all verification tests"""
    print("🚀 Starting Multi-Threading Setup Verification")
    print("=" * 60)
    
    tests = [
        ("Basic Imports", test_basic_imports),
        ("Thread Pool Setup", test_thread_pool_setup),
        ("Enhanced Video Service", test_enhanced_video_service),
        ("Async Functionality", test_async_functionality),
        ("Logging Setup", test_logging_setup),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name}: FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 VERIFICATION RESULTS")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Your multi-threading setup is ready!")
        print("🚀 You can now start your FastAPI server without issues.")
        return True
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please fix the issues before starting the server.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
