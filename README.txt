Astra 研究网站

本压缩包包含完整的静态网站：HTML、CSS、JavaScript、本地字体和图标、论文 PDF，以及当前网站使用的视频和封面。

预览
1. 解压，进入包含 index.html 的 astra-website 文件夹。
2. 在该目录运行：python3 -m http.server 8000
3. 浏览器打开 http://localhost:8000

发布
将 astra-website 文件夹里的内容上传到任意支持静态网站的托管服务。index.html 应位于网站根目录。

设置论文和代码链接
打开 links.js，填写 PROJECT_LINKS 中的 arxiv 和 code。
目前两个值均为空，首页保留对应图标但不会跳转。填入完整 https:// 地址后自动启用。

文件说明
- index.html：页面结构和正文
- style.css、dark.css、intro.css：样式
- app.js、motion.js、film.js、paired-playback.js：筛选、柱状图、开场和触觉配对播放
- media.js、geo-tasks.js：视频数据和任务简介
- links.js：arXiv / GitHub 地址
- assets/：论文、字体、图标、视频与封面

视频为网站展示副本，保留源播放速度；部分视频已压缩用于网页发布。
触觉 HDMI 两段原始时长不同，短片结束后停留在末帧；不代表逐帧对齐。
