import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(BASE_DIR)

if __name__ == '__main__':
    from core import tool

    argv_parser = tool.ManagementTool(sys.argv)
    argv_parser.execute()
