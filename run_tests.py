#!/usr/bin/env python
# run_tests.py - Test runner for YouTube Shorts Generator

import os
import sys
import unittest
from pathlib import Path


def run_all_tests():
    """Run all tests in the tests directory."""
    # Ensure we can import from the project root
    project_root = Path(__file__).parent
    sys.path.append(str(project_root))
    
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(project_root, 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1

def check_poetry_setup():
    """Verify Poetry configuration is correct."""
    print("\n--- Checking Poetry Configuration ---")
    try:
        import toml
        pyproject_path = Path(__file__).parent / 'pyproject.toml'
        
        if not pyproject_path.exists():
            print("❌ pyproject.toml not found!")
            return False
        
        config = toml.load(str(pyproject_path))
        
        # Check basic structure
        if 'project' not in config:
            print("❌ Missing [project] section in pyproject.toml")
            return False
            
        if 'build-system' not in config:
            print("❌ Missing [build-system] section in pyproject.toml") 
            return False
            
        # Check dependencies
        if 'dependencies' not in config['project']:
            print("❌ No dependencies defined in pyproject.toml")
            return False
            
        # Verify required dependencies for this project
        required_deps = ['openai', 'python-dotenv', 'moviepy']
        # Check if each required dependency exists in project dependencies
        missing_deps = [
            dep for dep in required_deps 
            if not any(dep in d.lower() for d in config['project']['dependencies'])
        ]
        
        if missing_deps:
            print(f"❌ Missing required dependencies: {', '.join(missing_deps)}")
            return False
            
        print("✅ Poetry configuration looks good!")
        print(f"📦 Found {len(config['project']['dependencies'])} dependencies")
        print(f"🏷️  Project version: {config['project']['version']}")
        
        return True
    except ImportError:
        print("❌ toml package not installed. Run: pip install toml")
        return False
    except Exception as e:
        print(f"❌ Error checking Poetry setup: {str(e)}")
        return False

if __name__ == "__main__":
    # Check Poetry setup if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--check-poetry":
        success = check_poetry_setup()
        sys.exit(0 if success else 1)
    else:
        # Run tests
        print("=== Running YouTube Shorts Generator Tests ===")
        sys.exit(run_all_tests())
