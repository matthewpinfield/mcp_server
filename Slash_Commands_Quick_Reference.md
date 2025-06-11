# ⚡ Slash Commands - Quick Reference

## 🧠 Memory (5 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/rule <text>` | Add preference/rule | `/rule I prefer TypeScript` |
| `/remember <info>` | Save information | `/remember Uses Firebase auth` |
| `/recall <query>` | Retrieve information | `/recall Firebase` |
| `/forget <query>` | Remove information | `/forget old settings` |
| `/stats` | Show memory stats | `/stats` |

## 🔧 Development (3 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/build [cmd]` | Build operations | `/build test` |
| `/package <eco> <query>` | Package search | `/package npm react` |
| `/analyze [type]` | Repository analysis | `/analyze structure` |

## 🔀 Git (3 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/status` | Git status | `/status` |
| `/commit <msg>` | Git commit | `/commit Add feature` |
| `/branch [action] [name]` | Branch ops | `/branch create feat` |

## 🛠️ System (4 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/commands [cat]` | List commands | `/commands memory` |
| `/help <cmd>` | Get help | `/help /rule` |
| `/add-command <name> <desc> <action>` | Add custom | `/add-command /deploy "Deploy" deploy_prod` |
| `/remove-command <name>` | Remove custom | `/remove-command /deploy` |

## 📁 Project (3 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/context` | Show context | `/context` |
| `/project [name] [desc]` | Set project | `/project MyApp "E-commerce"` |
| `/workspace [set] [val]` | Workspace settings | `/workspace theme dark` |

---

## 🚀 Common Workflows

**Setup Project:**
```bash
/project MyApp "Flutter e-commerce app"
/rule I prefer detailed explanations
/workspace theme dark
```

**Quick Development:**
```bash
/status
/build test
/commit "Add new feature"
/analyze metrics
```

**Memory Management:**
```bash
/remember "API endpoint: https://api.example.com"
/recall "API"
/stats
```

**Custom Commands:**
```bash
/add-command /deploy "Deploy to prod" deploy_prod
/commands custom
/help /deploy
```

---
## 💡 Tips
- Use `/commands` to discover all commands
- Use `/help <command>` for detailed usage
- Custom commands persist across sessions
- Memory integration keeps context alive
- Direct tool access = instant responses

**⚡ 17 built-in commands + unlimited custom commands = infinite possibilities!**