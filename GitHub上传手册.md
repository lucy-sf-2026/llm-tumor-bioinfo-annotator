# GitHub 开源上传手册

> 目标：把项目传到 GitHub，形成可展示、可复现的开源仓库。
> 前置：已创建好干净的文件夹 `C:\Users\你的用户名\Desktop\肿瘤项目_开源版`（26 个文件，0.32 MB）。

---

## 零、这个文件夹里有什么（已核对）

| 类别 | 文件 | 数量 |
|---|---|---|
| 程序 | app.py、config.py、enrich.py、gene_convert.py、pubmed_fetch.py、batch_pubmed.py、llm_summarize.py、test_llm.py | 8 |
| 教学页 | app_starter.py、step1_hello.py、step2_input.py、step3_button.py、step4_real.py | 5 |
| 数据 | genes.csv、gene_ids.csv、enrich_results.csv、pubmed_batch.csv、llm_summaries.csv | 5 |
| 文档 | README.md、项目流程手册.md、页面搭建手册.md、模块解耦手册.md | 4 |
| 配置 | requirements.txt、.gitignore、LICENSE（MIT） | 3 |

**已做过的安全处理：**

- ✅ 不含任何 `.bat` 文件（那两个含 API Key 的批处理已被排除）
- ✅ 扫描确认无 `sk-` 开头的密钥
- ✅ 扫描确认无个人邮箱（原手册里的 QQ 邮箱已替换为占位符）

⚠️ **但上传前你仍要自己再扫一遍**，见第四节。

---

## 一、路线选择

| 路线 | 适合 | 优点 | 缺点 |
|---|---|---|---|
| **A. 网页上传** | 首次上传 | 不用装任何东西 | 以后改代码要重新拖 |
| **B. GitHub Desktop** | 以后持续维护 | 改完点两下就同步 | 要装客户端（你已下载） |

**建议**：这次用 A 传上去，以后用 B 维护。或者直接用 B 一步到位。

---

## 二、路线 A：网页上传（最快）

### 第 1 步：注册 / 登录

打开 https://github.com ，右上角 **Sign up**（邮箱注册，不需要手机号），或直接 **Sign in**。

### 第 2 步：新建仓库

1. 右上角 **+** → **New repository**
2. 填写：

| 字段 | 填什么 |
|---|---|
| **Repository name** | `tumor-gene-annotation`（英文，小写，用连字符） |
| **Description** | `基于大模型的生物实体注释与文献挖掘工具` |
| 可见性 | 选 **Public**（开源要求） |
| Initialize | **三个都不要勾**（README / .gitignore / license 你都有现成的） |

3. 点 **Create repository**

### 第 3 步：进入上传页

创建后是空仓库页面，中间有一行：

> **…or upload an existing file**

点它。

### 第 4 步：拖文件

1. 打开文件夹：

```powershell
start "C:\Users\你的用户名\Desktop\肿瘤项目_开源版"
```

2. **全选**（`Ctrl+A`）→ 拖进浏览器上传区域
3. 等进度条走完（0.32 MB，很快）
4. 页面底部填提交信息：

```
初始版本：完整流水线（ID标准化/富集/文献/LLM约束）
```

5. 点 **Commit changes**

### 第 5 步：确认

刷新仓库首页，应该看到：

- README 自动渲染成富文本（标题、功能表、流水线图）
- 26 个文件
- LICENSE 显示 MIT

---

## 三、路线 B：GitHub Desktop（以后维护用）

安装包已下载在桌面：`GitHubDesktopSetup-x64.exe`（257 MB），双击安装即可，**不需要管理员权限**。

### 首次配置

1. 打开 GitHub Desktop → **Sign in to GitHub.com**
2. 用浏览器登录授权
3. 填 Name / Email（会出现在提交记录里）

### 导入项目

1. 菜单 **File → Add local repository**
2. 选 `C:\Users\你的用户名\Desktop\肿瘤项目_开源版`
3. 提示"不是 Git 仓库"时，点 **create a repository**
4. 弹窗里：
   - Name：`tumor-gene-annotation`
   - Description：同上
   - Git ignore：**None**（你有自己的 .gitignore）
   - License：**None**（你有自己的 LICENSE）
5. 点 **Create repository**

### 提交并发布

1. 左侧 **Changes** 会列出全部 26 个文件
2. 底部 Summary 填：`初始版本`
3. 点 **Commit to main**
4. 顶部点 **Publish repository**
5. **取消勾选** "Keep this code private"
6. 点 **Publish repository**

### 以后更新

改完代码 → Changes 里会出现改动 → 填 Summary → **Commit to main** → 顶部 **Push origin**。

---

## 四、上传前的安全检查（必做）

### 1. 扫描密钥

```powershell
cd "C:\Users\你的用户名\Desktop\肿瘤项目_开源版"
Select-String -Path * -Pattern "sk-","API_KEY=" -ErrorAction SilentlyContinue |
  Select-Object Filename, Line
```

**应该没有任何输出。** 如果有，把那行删掉再传。

### 2. 扫描个人信息

```powershell
Select-String -Path * -Pattern "@qq.com","@163.com","@gmail.com" -ErrorAction SilentlyContinue
```

同样应该为空。

### 3. 确认没有 bat

```powershell
Get-ChildItem *.bat
```

应该报错说找不到——那就对了。`run_llm.bat` 和 `test_llm.bat` 里写着你的 key，**绝对不能传**。

### 4. 看一眼文件列表

```powershell
Get-ChildItem | Select-Object Name
```

25 个，对得上第一节的清单就行。

---

## 五、上传后的检查（必做）

### 1. 在仓库里搜 key

打开仓库页面，按 `/` 打开搜索，输入 `sk-`。

**如果搜到任何东西，立刻删掉那个文件**（在文件页面点垃圾桶图标 → Commit）。

GitHub 上的密钥会被爬虫扫到，通常一分钟内就会被盗刷额度。

### 2. 确认 README 正常显示

仓库首页应该能看到：

- 标题「肿瘤基因注释与文献挖掘工具」
- 核心特性表格
- 流水线 ASCII 图
- 快速开始命令

如果显示成一堆纯文本，说明是 `.md` 后缀写错或文件名大小写不对。

### 3. 确认文件数

页面上应该显示 26 files。

---

## 六、以后怎么更新

改完本地代码后：

**路线 A（网页）**：进仓库 → 找到那个文件 → 铅笔图标编辑 → 或 Add file → Upload files 覆盖 → Commit

**路线 B（Desktop）**：Changes → Commit to main → Push origin

**每次更新记得**：`llm_summaries.csv` 如果重跑过，要重新拖一份覆盖。

---

## 七、常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| 拖拽没反应 | 浏览器不支持文件夹拖拽 | 进文件夹全选文件再拖，别拖文件夹 |
| 提示文件太大 | 单文件超 25 MB | 你的最大 140 KB，不会遇到 |
| 中文文件名乱码 | 编码问题 | 一般正常；若乱码，改成英文名再传 |
| README 不显示 | 文件名不是 `README.md` | 确认大小写 |
| 想改成私有 | — | Settings → 最下方 Danger Zone → Change visibility |
| 传错了想删 | — | 文件页 → 垃圾桶 → Commit |
| 忘了 .gitignore | 后续会传 `__pycache__` | 网页上传时手动不选那个文件夹即可 |

---

## 八、答辩时能展示什么

打开仓库首页，指出：

1. **README 的流水线图** —— 一眼看懂架构
2. **防幻觉设计那一节** —— 核心创新点
3. **requirements.txt** —— 环境可复现
4. **LICENSE** —— 开源规范
5. **提交历史** —— 有迭代过程

被问"代码能跑吗"，答：**装完依赖、填一个邮箱就能跑**，README 的快速开始有完整命令。

---

## 九、检查清单（照着打勾）

- [ ] 文件夹 `肿瘤项目_开源版` 有 26 个文件
- [ ] 密钥扫描无结果
- [ ] 邮箱扫描无结果
- [ ] 没有 `.bat` 文件
- [ ] GitHub 已建仓库（Public）
- [ ] 26 个文件全部上传
- [ ] 仓库首页 README 正常渲染
- [ ] 仓库内搜索 `sk-` 无结果
- [ ] LICENSE 显示 MIT
- [ ] 记下仓库地址：`https://github.com/你的用户名/tumor-gene-annotation`
