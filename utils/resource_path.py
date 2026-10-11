# resource_path.py
import sys, os

def resource_path(*parts: str) -> str:
    """
    获取资源文件的绝对路径。
    - dev 模式(直接 python main.py):用脚本所在目录
    - 打包后:用 exe所在目录(os.path.dirname(sys.executable))
    
    注意:对于 _internal 里的资源,用 sys._MEIPASS;
 对于放在 exe 同级目录的资源,用 sys.executable 的 dirname。
    """
    if getattr(sys, 'frozen', False):
        # 打包后:exe 同级目录
        base = os.path.dirname(sys.executable)
    else:
        # 开发模式:脚本所在目录
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)