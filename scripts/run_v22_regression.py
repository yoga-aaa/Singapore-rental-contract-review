"""Version-bound v22 entrypoint. Default is free preflight, not inference."""
from run_v18_regression import main

if __name__ == '__main__':
    main('v22')
