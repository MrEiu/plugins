# Kapsel Lang Plugin (`lang`)

Instant terminal environment language, shell culture, and CLI localization switcher for Kapsel.

## Features

- ⚡ **Zero Latency**: Switches environment in 0ms without restarting your terminal.
- 🌏 **Full-Stack Localization Synchronization**:
  - `LANG`, `LC_ALL`, `LC_MESSAGES`, `LANGUAGE`
  - Windows PowerShell `.NET` thread culture (`CurrentUICulture = 'zh-CN' / 'en-US'`)
  - `DOTNET_CLI_UI_LANGUAGE` (for .NET SDK and MSBuild)
  - `VSLANG` (Visual Studio tools)
  - Kapsel Capsule UI language (`language: zh_CN / en`)
- 🔄 **One-Touch Toggle**: Simply run `lang` without arguments to flip between Chinese and English.

## Usage

```bash
lang            # Toggle between Chinese and English
lang zh         # Switch terminal environment to Simplified Chinese
lang en         # Switch terminal environment to English
lang status     # View active locale, culture, and environment variables
```
