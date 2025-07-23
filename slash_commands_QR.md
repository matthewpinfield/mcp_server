# Slash Commands - Quick Reference

## Memory (10 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/rule <text>` | Add rule | `/rule I prefer detailed code explanations` |
| `/recall <query>` | Retrieve information | `/recall state management` |
| `/forget <query>` | Remove information | `/forget old project rules` |
| `/correct <text>` | Correct AI response | `/correct Use async/await instead` |
| `/fix <text>` | Fix AI response (alias) | `/fix The correct syntax is setState` |
| `/list_rules [search]` | List rules with IDs | `/list_rules coding` |
| `/delete_rule <id>` | Delete rule by ID | `/delete_rule ab12cd34` |
| `/change_rule <id> <text>` | Update rule by ID | `/change_rule ab12cd34 I prefer Vue` |
| `/memories [search]` | Show all memories | `/memories coding` |

## Development (3 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/build [cmd]` | Build command execution | `/build test` |
| `/package <eco> <query>` | Package search | `/package npm react-router` |
| `/analyze [type]` | Repository analysis | `/analyze structure` |

## Git (4 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/status` | Git status check | `/status` |
| `/commit <msg>` | Git commit | `/commit Fix authentication bug` |
| `/branch [action] [name]` | Branch operations | `/branch create feature-auth` |

## System (4 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/commands [cat]` | List commands | `/commands memory` |
| `/help <cmd>` | Get help for command | `/help /remember` |
| `/add-command <name> <desc> <action>` | Add custom command | `/add-command /deploy 'Deploy to prod' deploy_prod` |
| `/remove-command <name>` | Remove custom command | `/remove-command /deploy` |

## Project (2 commands)
| Command | Purpose | Example |
|---------|---------|---------|
| `/context` | Show session context | `/context` |
| `/project [name] [desc]` | Set project info | `/project MyApp 'Flutter e-commerce app'` |

---

## 🚀 Common Workflows

**Setup Project:**
```bash
/project MyApp "Flutter e-commerce app"
/rule I prefer detailed explanations
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
/rule I prefer detailed code comments
/remember "API endpoint: https://api.example.com"
/list_rules coding
/change_rule ab12cd34 I prefer concise comments
/recall "API"
/memories coding
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

**⚡ 21 built-in commands + unlimited custom commands = infinite possibilities!**