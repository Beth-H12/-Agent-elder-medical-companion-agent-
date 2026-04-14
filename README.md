# 银龄就医陪诊 Agent

一个面向老年人的任务型 Multi-Agent 就医陪诊项目。

它不是普通聊天机器人，而是把“说出症状 -> 推荐医院 -> 查看挂号与到院提醒 -> 保存检查资料”串成一个完整流程，重点解决老年人就医时常见的几个难点：

- 不知道该挂什么科
- 不知道附近哪家医院更合适
- 看不懂挂号后的到院路线和候诊位置
- 检查单、报告图太多，不会整理

## 项目亮点

- 本地 LLM 分诊：默认接入 `Ollama + Qwen3`
- 多 Agent 协作：分诊、推荐、挂号、导航、归档、提醒分开实现
- 真实路线规划：接入高德地图 Web 服务
- 老年友好前端：大字体、重点加粗、图标化信息、模块跳转
- 文档归档：支持上传图片，自动按 `日期-科室/有问题|无问题` 存储
- 可持续服务：所有 session、挂号结果、文档摘要、Agent trace 都会持久化

## 适合展示的项目定位

这个项目更适合作为：

- 求职作品集项目
- 毕设 / 课程设计
- 医疗 Agent / Multi-Agent demo
- 智慧养老 / 老年友好交互系统 demo

## 当前已实现的功能

### 1. 症状分诊

- 支持老人自然语言输入
- 优先走本地 `Ollama` 模型输出结构化分诊结果
- 模型不可用时自动回退到规则分诊
- 加入了面向老年人的更谨慎分诊规则

### 2. 医院推荐

- 支持根据当前位置、出行方式、时间偏好推荐医院
- 普通场景下：综合考虑路程、换乘、医院匹配度、拥挤度
- 西安场景下：内置“二甲 / 三甲优先库”
- 支持返回医院官网入口

### 3. 挂号与到院提醒

- 根据候选医院生成挂号结果
- 显示挂号时间、签到时间、候诊位置
- 显示详细到院路线
- 支持老人直接点击医院候选项继续下一步

### 4. 检查资料归档

- 支持上传图片
- 支持补充文字说明
- 支持“有问题 / 无问题”分类
- 自动保存到：
  `static/medical_records/日期-科室/有问题或无问题/`

### 5. 老年友好前端

- 字号调节
- 模块快捷跳转
- 结果区折叠 / 展开
- 更柔和的渐变界面
- 重点信息加粗与图标化

## 核心技术栈

### 后端框架

- `FastAPI`
  负责整个 HTTP API 服务，是项目的主后端框架。

### 数据建模

- `Pydantic`
  负责请求参数、响应结构、Agent 之间的数据结构校验。

### 数据库存储

- `SQLAlchemy`
  负责 ORM 和数据库持久化。
- `SQLite`
  默认开发数据库。
- `PostgreSQL`
  可以通过环境变量切换成正式数据库。

### 本地大模型

- `Ollama`
  负责本地模型运行。
- `Qwen3`
  负责结构化分诊输出。

### 外部服务

- `高德地图 Web 服务 API`
  用于地理编码、医院搜索、步行/公交/地铁/驾车路径规划。

### 前端

- 原生 `HTML + CSS + JavaScript`
  当前前端刻意保持轻量，方便演示、部署和改样式。

### 测试

- `pytest`
  负责接口级测试和关键流程回归测试。

## 快速启动

### 1. 安装依赖

```bash
py -m pip install -r requirements.txt
```

### 2. 配置环境变量

先复制模板：

```bash
copy .env.example .env
```

至少需要确认这些配置：

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:1.7b
MAP_PROVIDER=amap
AMAP_API_KEY=你的高德Key
DATABASE_URL=sqlite:///./silvercare.db
```

### 3. 启动 Ollama

确保本地已经安装 Ollama，并拉取好模型：

```bash
ollama pull qwen3:1.7b
```

### 4. 启动服务

```bash
py run_local.py
```

或者：

```bash
py -m uvicorn app.main:app --reload
```

### 5. 访问页面

- 首页：[http://127.0.0.1:8000](http://127.0.0.1:8000)
- 接口文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 项目整体流程

```text
用户输入症状
-> 分诊 Agent 判断科室和紧急程度
-> 医院推荐 Agent 结合地图和规则筛选候选医院
-> 挂号 Agent 生成挂号结果
-> 导航 Agent 生成到院与候诊提醒
-> 文档 Agent 和提醒 Agent 保存检查资料、生成后续建议
```

## 目录结构

```text
app/
  agents/      Agent 层，负责具体业务任务
  api/         FastAPI 路由
  core/        配置管理
  data/        内置医院种子数据
  db/          数据库初始化和 ORM 模型
  schemas/     Pydantic 数据模型
  services/    外部能力和基础服务
  utils/       通用工具函数
static/        演示前端
tests/         自动化测试
run_local.py   本地启动脚本
requirements.txt
README.md
```

更详细的架构说明在这里：

- [项目架构说明](./docs/PROJECT_ARCHITECTURE.md)

## GitHub 上传前建议

这个仓库已经按 GitHub 公开项目做了整理：

- `.env` 已被 `.gitignore` 忽略
- 本地数据库 `silvercare.db` 已忽略
- 运行期上传图片目录 `static/uploads/` 已忽略
- 运行期归档目录 `static/medical_records/` 已忽略
- `__pycache__`、`.pytest_cache`、`.idea` 已忽略
- 已增加 GitHub Actions 自动测试工作流

上传时建议保留：

- `app/`
- `static/`
- `tests/`
- `.env.example`
- `.gitignore`
- `README.md`
- `requirements.txt`
- `run_local.py`
- `docs/`
- `.github/`

## GitHub Actions

仓库里已经提供了基础 CI：

- 安装依赖
- 运行 `pytest`

文件位置：

- [ci.yml](./.github/workflows/ci.yml)

## 当前边界

这套系统已经是“可运行的完整演示项目”，但也有清晰边界：

- 分诊是“门诊分诊建议”，不是医学诊断
- 挂号目前是“官方入口引导 + mock 号源逻辑”，不是统一自动抢号
- 文档上传目前是“图片保存 + 文字归档”，不是完整 OCR 医疗识别系统

## 下一步可以继续扩展

- 接入 OCR，把图片直接转成文字摘要
- 把挂号从 mock 进一步做成平台适配器
- 把前端改成 React / Next.js 版本
- 给 session 增加用户登录和历史查询页
- 补更多城市的优先医院库

## 运行测试

```bash
py -m pytest -q
```
