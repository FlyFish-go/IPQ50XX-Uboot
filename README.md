# IPQ50XX-Uboot

给高通 IPQ50xx 路由器装一个好用的 U-Boot：网页救砖、照原厂逻辑的双系统、写入前逐项核对。

安装指南网站：<https://flyfish-go.github.io/IPQ50XX-Uboot/>

## 目录

| 路径 | 内容 |
|---|---|
| `devices/` | 每个机型一份资料（YAML），网站和安装程序都从这里读取 |
| `docs/` | 安装指南网站（VitePress） |

## 本地预览网站

```sh
npm ci
npm run docs:dev
```

## 添加一个机型

复制 `devices/` 下一个现有文件，改成新机型的资料，文件名与 `id` 一致。`status` 只能是 `verified`、`community`、`testing`、`planned` 之一。

本项目与各路由器厂商无关。
