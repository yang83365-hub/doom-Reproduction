# doom-Reproduction
本作品是对doom的拙劣模仿，有兴趣的朋友可以下载体验
运行你的程序只需要安装以下三个第三方Python库：
**pygame**（用于窗ロ管理、事件捕捉和音频处理）
**numpy**（用于高效计算音效波形数组）
**PyOpenGL**（OpenGL.GL接口实现3D图行渲染）
运行该程序所需的一次性安装命令如下：
pip install pygame numpy PyOpenGL
如果使用的是 macOS 或 Linux，且默认配置为 Python 3，则可以使用：
pip3 install pygame numpy PyOpenGL

🎮 游戏操作指南
 视角控制：移动鼠标控制角色左右旋转、上下看（Pitch 轴抬头/低头）。
 移动：⁠W⁠ (前进)、⁠S⁠ (后退)、⁠A⁠ (左移)、⁠D⁠ (右移)。
 跳跃：⁠空格键 (Space)⁠。
 射击：⁠鼠标左键⁠。
 关卡/剧情推进：在主菜单、死亡或过场剧情中，按下 ⁠空格键⁠、⁠ESC⁠ 或 ⁠点击鼠标左键⁠ 继续。
 保存并退出：在游戏进行中按 ⁠ESC⁠ 键可将当前关卡、击杀和死亡数据自动保存至本地 ⁠save.json⁠ 并返回主菜单。
"""
