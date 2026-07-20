"""生成简历 PDF —— 基于 RAG 多文档智能问答系统替换即时通讯项目。

布局参照原简历：
- A4 单页（595 x 842 pt）
- 左侧栏（约 200pt 宽）深色背景：姓名、基本信息、求职意向、技能、奖状
- 右侧主体白底：项目经历
- 顶部深色横条标题

使用 PyMuPDF 的 insert_text（精确坐标）而非 insert_textbox（自动布局但易溢出失败）。
手动实现文字换行，确保所有内容都能渲染出来。
"""
import fitz  # PyMuPDF


# ============ 颜色定义（0-1 浮点范围）============
def _c(r, g, b):
    return (r / 255.0, g / 255.0, b / 255.0)

NAVY = _c(0x3F, 0x3F, 0x6E)       # 深蓝紫（左侧栏 + 标题块）
ACCENT = _c(0x63, 0x66, 0xF1)     # 靛蓝强调色
DARK_TEXT = _c(0x26, 0x21, 0x5C)  # 主文本深色
MUTED = _c(0x5F, 0x5E, 0x5A)      # 次要文本
WHITE = (1, 1, 1)
LIGHT_BG = _c(0xF5, 0xF3, 0xFF)   # 浅紫背景
LABEL_LIGHT = _c(0xC9, 0xCB, 0xF6)  # 浅色标签文字（深底用）
BORDER_LIGHT = _c(0xE5, 0xE7, 0xEB)  # 浅色分隔线

# ============ 字体 ============
FONT_REG = "msyh"
FONT_BOLD = "msyhbd"
FONT_SUN = "simsun"

FONT_REG_PATH = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD_PATH = "C:/Windows/Fonts/msyhbd.ttc"
FONT_SUN_PATH = "C:/Windows/Fonts/simsun.ttc"


def estimate_text_width(text, fontsize=9):
    """估算文本渲染宽度（pt）。中文约 fontsize*1.0，英文/数字约 fontsize*0.55。"""
    width = 0.0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            width += fontsize * 1.0
        else:
            width += fontsize * 0.55
    return width


def wrap_by_width(text, max_width, fontsize=9):
    """按视觉宽度换行，返回行列表。"""
    lines = []
    current = ""
    current_w = 0.0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            ch_w = fontsize * 1.0
        else:
            ch_w = fontsize * 0.55
        if current_w + ch_w > max_width and current:
            lines.append(current)
            current = ch
            current_w = ch_w
        else:
            current += ch
            current_w += ch_w
    if current:
        lines.append(current)
    return lines


def draw_text(page, x, y, text, fontname=FONT_REG, fontsize=9, color=DARK_TEXT):
    """在 (x, y) 基线位置绘制单行文本。y 是基线 y 坐标。"""
    page.insert_text(
        fitz.Point(x, y),
        text,
        fontname=fontname,
        fontsize=fontsize,
        color=color,
    )


def draw_wrapped_text(page, x, y, x_end, text, fontname=FONT_REG, fontsize=9,
                      color=DARK_TEXT, line_height=13, first_line_prefix="",
                      prefix_fontname=None, prefix_color=None):
    """绘制自动换行文本，可带加粗的行首前缀（如"项目描述："）。

    y 是第一行的基线 y 坐标。
    返回最后一行之后的 y 坐标（即下一行基线位置）。
    """
    if prefix_fontname is None:
        prefix_fontname = fontname
    if prefix_color is None:
        prefix_color = color

    max_width = x_end - x

    if first_line_prefix:
        prefix_w = estimate_text_width(first_line_prefix, fontsize)
        # 第一行：前缀 + 部分正文
        first_max = max_width - prefix_w
        first_lines = wrap_by_width(text, first_max, fontsize)
        first_line_text = first_lines[0] if first_lines else ""
        remaining_lines = first_lines[1:] if len(first_lines) > 1 else []

        # 绘制前缀
        draw_text(page, x, y, first_line_prefix, fontname=prefix_fontname,
                  fontsize=fontsize, color=prefix_color)
        # 绘制第一行正文
        draw_text(page, x + prefix_w, y, first_line_text, fontname=fontname,
                  fontsize=fontsize, color=color)
        y += line_height

        # 后续行
        for line in remaining_lines:
            draw_text(page, x, y, line, fontname=fontname, fontsize=fontsize, color=color)
            y += line_height
    else:
        all_lines = wrap_by_width(text, max_width, fontsize)
        for line in all_lines:
            draw_text(page, x, y, line, fontname=fontname, fontsize=fontsize, color=color)
            y += line_height

    return y


def build_resume(output_path: str):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # 注册字体
    page.insert_font(fontname=FONT_REG, fontfile=FONT_REG_PATH)
    page.insert_font(fontname=FONT_BOLD, fontfile=FONT_BOLD_PATH)
    page.insert_font(fontname=FONT_SUN, fontfile=FONT_SUN_PATH)

    # ============ 左侧栏背景（深色）============
    sidebar_x1 = 200
    page.draw_rect(fitz.Rect(0, 0, sidebar_x1, 842), color=NAVY, fill=NAVY)

    # ============ 顶部标题块 ============
    page.draw_rect(fitz.Rect(0, 0, 595, 70), color=NAVY, fill=NAVY)

    # "简历"
    draw_text(page, 55, 45, "简历", fontname=FONT_SUN, fontsize=22, color=WHITE)
    # "RESUME"
    draw_text(page, 135, 45, "RESUME", fontname=FONT_REG, fontsize=11, color=LABEL_LIGHT)

    # ============ 左侧栏内容 ============
    cx = 30

    # ---- 个人信息 ----
    y = 100
    info_items = [
        ("姓名：", "谢敬南"),
        ("性别：", "男"),
        ("学历：", "本科"),
        ("专业：", "机器人工程"),
        ("毕业院校：", "哈尔滨理工大学"),
        ("英语水平：", "CET-6"),
        ("毕业时间：", "2027.6.1"),
    ]
    for label, value in info_items:
        draw_text(page, cx, y, label, fontname=FONT_BOLD, fontsize=9.5, color=WHITE)
        label_w = estimate_text_width(label, 9.5)
        draw_text(page, cx + label_w, y, value, fontname=FONT_REG, fontsize=9.5, color=WHITE)
        y += 22

    # ---- 联系方式 ----
    y += 5
    contact_items = [
        ("邮箱：", "18651522512@163.com"),
        ("电话：", "18651522512"),
    ]
    for label, value in contact_items:
        draw_text(page, cx, y, label, fontname=FONT_BOLD, fontsize=9.5, color=WHITE)
        label_w = estimate_text_width(label, 9.5)
        # 邮箱较长，缩小字号
        fs = 8 if "163" in value else 9.5
        draw_text(page, cx + label_w, y, value, fontname=FONT_REG, fontsize=fs, color=WHITE)
        y += 22

    # ---- 技术技能 ----
    y += 10
    page.draw_rect(fitz.Rect(cx - 5, y - 12, sidebar_x1 - 10, y + 6), color=ACCENT, fill=ACCENT)
    draw_text(page, cx, y, "技术技能", fontname=FONT_BOLD, fontsize=11, color=WHITE)
    y += 22

    skills = [
        ("C/C++：", "熟悉面向对象及面向过程编程思想，熟悉C++11特性（如Lambda、右值引用、智能指针等）及STL标准库；"),
        ("数据结构与算法：", "掌握栈、队列、链表、二叉树、哈希表等数据结构；熟悉动态规划、递归分治、DFS/BFS、贪心等算法思想；"),
        ("计算机网络：", "熟悉TCP/UDP协议、Socket编程；熟悉HTTP1.0、2.0协议；熟悉HTTPS加密原理；"),
        ("Linux操作系统：", "熟悉Linux基本命令，熟悉I/O多路复用模型；熟悉Epoll ET模式、进程与线程、信号、管道、内存映射、线程池；"),
        ("MySQL数据库：", "熟悉MySQL常用语句（查询、更改、删除等），了解事务ACID特性和索引原理；"),
        ("Python/AI：", "熟悉Python开发，掌握FastAPI、PyMuPDF、SQLAlchemy等框架；了解RAG、Embedding、向量检索、LLM应用开发；"),
        ("AI编程工具：", "熟练使用Claude Code、Cursor、Trae等AI编程工具，了解上下文管理、记忆、Skills、Agent、Workflow、MCP、CLI等。"),
    ]
    avail_w = sidebar_x1 - 10 - cx
    for label, desc in skills:
        # 标签单独一行（深色背景上用浅色）
        draw_text(page, cx, y, label, fontname=FONT_BOLD, fontsize=8.5, color=LABEL_LIGHT)
        y += 11
        # 描述自动换行
        y = draw_wrapped_text(page, cx, y, sidebar_x1 - 10, desc,
                              fontname=FONT_REG, fontsize=8, color=WHITE, line_height=10.5)
        y += 5

    # ---- 奖状证书 ----
    y += 5
    page.draw_rect(fitz.Rect(cx - 5, y - 12, sidebar_x1 - 10, y + 6), color=ACCENT, fill=ACCENT)
    draw_text(page, cx, y, "奖状证书", fontname=FONT_BOLD, fontsize=11, color=WHITE)
    y += 22
    certs = [
        ("2025年", "荣获校级三好学生"),
        ("2024年", "荣获“挑战杯”省级三等奖"),
    ]
    for year, cert in certs:
        draw_text(page, cx, y, year, fontname=FONT_REG, fontsize=9, color=LABEL_LIGHT)
        draw_text(page, cx + 50, y, cert, fontname=FONT_REG, fontsize=9, color=WHITE)
        y += 20

    # ============ 右侧主体：项目经历 ============
    main_x0 = 220
    main_x1 = 575

    # 标题块
    page.draw_rect(fitz.Rect(main_x0, 90, main_x1, 115), color=NAVY, fill=NAVY)
    draw_text(page, main_x0 + 10, 108, "项目经历", fontname=FONT_BOLD, fontsize=13, color=WHITE)

    y = 135
    main_avail_w = main_x1 - main_x0 - 5

    # ============ 项目一：短视频播放器 ============
    draw_text(page, main_x0, y, "基于Qt/Linux的短视频播放器",
              fontname=FONT_BOLD, fontsize=11, color=ACCENT)
    y += 16
    draw_text(page, main_x0, y, "Qt · Linux · FFmpeg 4.2.2 · SDL2 · OpenGL · Nginx-RTMP · MySQL · epoll",
              fontname=FONT_REG, fontsize=7.5, color=MUTED)
    y += 14

    desc1 = "基于Qt/Linux开发的短视频播放器应用，集成FFmpeg 4.2.2实现视频编解码与音视频同步，使用SDL2处理音频，OpenGL实现高性能渲染。支持本地视频播放、网络RTMP流播放，具备用户注册登录、视频上传下载功能。"
    y = draw_wrapped_text(page, main_x0, y, main_x1, desc1,
                          fontsize=9, color=DARK_TEXT, line_height=12,
                          first_line_prefix="项目描述：", prefix_color=DARK_TEXT)
    y += 3

    modules1 = [
        ("视频播放实现架构：", "服务端epoll+线程池+MySQL，Nginx-RTMP支持推拉流分发，上传时自动将视频转封装为HLS分片，客户端可通过url拉m3u8文件播放，实现音视频同步处理、播放、暂停、进度条控制等功能；"),
        ("多线程优化：", "Qt中实现视频解码、音频播放、网络通信并行处理，使用数据缓存队列保证数据流畅传输；"),
        ("网络功能与模块化：", "采用中介者模式封装网络通信层，支持视频文件上传和下载，视频播放核心与界面分离；"),
        ("预览图与帧补偿：", "基于FFmpeg解码提取I帧实现自动封面生成，QProcess合成为GIF预览图，实现帧补偿同步算法，同步误差控制在1帧以内；"),
        ("问题解决：", "实现FLUSH包+avcodec_flush_buffers的seek跳转机制，解决跳转后花屏问题。"),
    ]
    for label, text in modules1:
        y = draw_wrapped_text(page, main_x0, y, main_x1, text,
                              fontsize=9, color=DARK_TEXT, line_height=12,
                              first_line_prefix=label, prefix_color=ACCENT)
        y += 3

    y += 10

    # ============ 项目二：基于 RAG 的多文档智能问答系统 ============
    draw_text(page, main_x0, y, "基于RAG的多文档智能问答系统",
              fontname=FONT_BOLD, fontsize=11, color=ACCENT)
    y += 16
    draw_text(page, main_x0, y, "FastAPI · FAISS · BGE(Embedding+Reranker) · DeepSeek LLM · Vue3 · SQLAlchemy · Docker",
              fontname=FONT_REG, fontsize=7.5, color=MUTED)
    y += 14

    desc2 = "独立设计并全栈实现的检索增强生成（RAG）问答系统，支持PDF/Word/Markdown三种格式文档的上传、解析、向量化与语义检索。采用「API路由→业务编排→数据访问→ORM」四层架构，后端约3500行Python，前端约1500行TypeScript，针对延迟、成本、准确性做了6项工程优化。"
    y = draw_wrapped_text(page, main_x0, y, main_x1, desc2,
                          fontsize=9, color=DARK_TEXT, line_height=12,
                          first_line_prefix="项目描述：", prefix_color=DARK_TEXT)
    y += 3

    modules2 = [
        ("检索增强管线：", "基于BGE-small-zh向量化 + FAISS IndexFlatIP索引实现毫秒级语义检索，引入CrossEncoder二次重排（Rerank）提升相关性，支持按文档范围过滤检索；"),
        ("SSE流式输出：", "实现流式问答接口，后端yield结构化事件流（meta→sources→delta→done），前端用fetch+ReadableStream解析SSE，实现逐token实时渲染；"),
        ("语义缓存层：", "设计进程内语义缓存单例（LRU+线程安全），通过余弦相似度匹配历史问题，相似度≥0.98时直接返回缓存，高频提问延迟从77s降至0.02s，加速3800倍；"),
        ("双模式问答：", "支持strict（严格依据文档、检索不足拒答+Verifier二次校验）和open（允许补充说明）两种模式，Verifier使用LLM JSON Mode强制结构化输出；"),
        ("多路召回与HyDE：", "实现Multi-Query变种并集检索（LLM生成N个问题变种，按chunk_id去重保留最高分）与HyDE假设性文档检索，提升召回覆盖率；"),
        ("Context Token管理：", "按rerank_score降序累加token，超预算时截断低分片段，历史对话保留末尾，避免超出LLM context window；"),
        ("工程化能力：", "懒加载+单例模式（模型/索引首次使用才加载），LLM调用3次重试+指数退避，Verifier双路径容错（JSON Mode→正则退化），Docker一键部署。"),
    ]
    for label, text in modules2:
        y = draw_wrapped_text(page, main_x0, y, main_x1, text,
                              fontsize=9, color=DARK_TEXT, line_height=12,
                              first_line_prefix=label, prefix_color=ACCENT)
        y += 2

    # ============ 底部装饰线 ============
    page.draw_line(fitz.Point(main_x0, 835), fitz.Point(main_x1, 835),
                   color=BORDER_LIGHT, width=0.5)

    # 保存
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"简历已生成: {output_path}")


if __name__ == "__main__":
    import os
    output = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "谢敬南-C++-本科-哈尔滨理工大学-2027-RAG版.pdf")
    build_resume(output)
