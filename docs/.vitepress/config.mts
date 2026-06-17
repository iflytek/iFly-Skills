import { defineConfig } from "vitepress";

const base = process.env.DOCS_BASE || "/";

const socialLinks = [
  { icon: "github", link: "https://github.com/iflytek/iFly-Skills" }
];

const editLinkPattern = "https://github.com/iflytek/iFly-Skills/edit/main/docs/:path";

export default defineConfig({
  title: "iFly-Skills",
  description: "Official collection of iFLYTEK AI skills for agent ecosystems and developer workflows.",
  base,
  cleanUrls: true,
  ignoreDeadLinks: true,
  locales: {
    root: {
      label: "English",
      lang: "en-US",
      title: "iFly-Skills",
      description: "Official collection of iFLYTEK AI skills for agent ecosystems and developer workflows.",
      themeConfig: {
        siteTitle: "iFly-Skills",
        nav: [
          { text: "Home", link: "/" },
          { text: "Quick Start", link: "/guide/quick-start" },
          { text: "Skills", link: "/skills/" },
          { text: "FAQ", link: "/faq" },
          { text: "Contributing", link: "/CONTRIBUTING" }
        ],
        sidebar: [
          {
            text: "Getting Started",
            items: [
              { text: "Overview", link: "/guide/" },
              { text: "Quick Start", link: "/guide/quick-start" },
              { text: "FAQ", link: "/faq" }
            ]
          },
          {
            text: "Skills",
            items: [
              { text: "Skill Catalog", link: "/skills/" }
            ]
          },
          {
            text: "Contribution",
            items: [
              { text: "Contributing Guide", link: "/CONTRIBUTING" },
              { text: "Contribute to the Docs", link: "/contribute-to-docs" }
            ]
          }
        ],
        socialLinks,
        search: {
          provider: "local"
        },
        editLink: {
          pattern: editLinkPattern,
          text: "Edit this page on GitHub"
        },
        langMenuLabel: "Languages",
        returnToTopLabel: "Back to top",
        sidebarMenuLabel: "Menu",
        darkModeSwitchLabel: "Theme",
        outline: {
          label: "On this page"
        },
        docFooter: {
          prev: "Previous page",
          next: "Next page"
        },
        footer: {
          message: "Apache 2.0 Licensed.",
          copyright: "Copyright © iFLYTEK iFly-Skills"
        }
      }
    },
    zh: {
      label: "简体中文",
      lang: "zh-CN",
      link: "/zh/",
      title: "iFly-Skills",
      description: "科大讯飞面向智能体生态系统和开发者工作流的官方 AI 技能集合文档站。",
      themeConfig: {
        siteTitle: "iFly-Skills",
        nav: [
          { text: "首页", link: "/zh/" },
          { text: "快速开始", link: "/zh/guide/quick-start" },
          { text: "技能列表", link: "/zh/skills/" },
          { text: "FAQ", link: "/zh/faq" },
          { text: "贡献协作", link: "/zh/CONTRIBUTING" }
        ],
        sidebar: [
          {
            text: "开始使用",
            items: [
              { text: "概览", link: "/zh/guide/" },
              { text: "快速开始", link: "/zh/guide/quick-start" },
              { text: "FAQ", link: "/zh/faq" }
            ]
          },
          {
            text: "技能",
            items: [
              { text: "技能列表", link: "/zh/skills/" }
            ]
          },
          {
            text: "贡献协作",
            items: [
              { text: "贡献指南", link: "/zh/CONTRIBUTING" },
              { text: "为文档站做贡献", link: "/zh/contribute-to-docs" }
            ]
          }
        ],
        socialLinks,
        search: {
          provider: "local"
        },
        editLink: {
          pattern: editLinkPattern,
          text: "在 GitHub 上编辑此页"
        },
        langMenuLabel: "语言",
        returnToTopLabel: "返回顶部",
        sidebarMenuLabel: "菜单",
        darkModeSwitchLabel: "主题",
        outline: {
          label: "页面导航"
        },
        docFooter: {
          prev: "上一页",
          next: "下一页"
        },
        footer: {
          message: "Apache 2.0 Licensed.",
          copyright: "Copyright © iFLYTEK iFly-Skills"
        }
      }
    }
  }
});
