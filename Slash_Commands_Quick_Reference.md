# ⚡ Slash Commands - Quick Reference

## 🧠 Memory (8 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/rule <text>` | Add preference/rule | `/rule I prefer TypeScript` |
| `/list_rules [search]` | List rules with IDs | `/list_rules coding` |
| `/delete_rule <id>` | Delete rule by ID | `/delete_rule ab12cd34` |
| `/change_rule <id> <text>` | Update rule by ID | `/change_rule ab12cd34 I prefer Vue` |
| `/remember <info>` | Save information | `/remember Uses Firebase auth` |
| `/recall <query>` | Retrieve information | `/recall Firebase` |
| `/forget <query>` | Remove information | `/forget old settings` |

## 🔧 Development (3 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/build [cmd]` | Build operations | `/build test` |
| `/package <eco> <query>` | Package search | `/package npm react` |
| `/analyze [type]` | Repository analysis | `/analyze structure` |

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
/build test
/analyze metrics
```

**Memory Management:**
```bash
/rule I prefer detailed code comments
/remember "API endpoint: https://api.example.com"
/list_rules coding
/change_rule ab12cd34 I prefer concise comments
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