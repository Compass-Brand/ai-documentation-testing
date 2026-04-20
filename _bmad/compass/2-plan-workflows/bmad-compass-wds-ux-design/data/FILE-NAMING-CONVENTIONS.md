# WDS Agent File Naming Conventions

**For**: All WDS Agents (Freya, Saga, Idunn)
**Purpose**: Consistent file naming across all WDS projects
**Version**: 1.0

---

## 🎯 Core Principle

**Use descriptive, specific file names - NOT generic names like "README"**

---

## ❌ DON'T Use Generic Names

### Never Create:
- ❌ `README.md` (too generic, confusing when multiple exist)
- ❌ `INSTRUCTIONS.md` (instructions for what?)
- ❌ `GUIDE.md` (guide for what?)
- ❌ `NOTES.md` (notes about what?)
- ❌ `INFO.md` (info about what?)

**Problem**: When there are 5 README files, which one do you read?

---

## ✅ DO Use Specific Names

### Always Create:
- ✅ `AGENTIC-DEVELOPMENT-GUIDE.md` (specific topic)
- ✅ `FREYA-WORKFLOW-INSTRUCTIONS.md` (specific agent + purpose)
- ✅ `PROTOTYPE-ROADMAP.md` (specific purpose)
- ✅ `PROJECT-ANALYSIS-ROUTER.md` (specific function)
- ✅ `COMPONENT-NAMING-CONVENTIONS.md` (specific topic)

**Benefit**: Clear, self-documenting, no confusion

---

## 📋 Naming Patterns

### Pattern 1: [TOPIC]-GUIDE.md
**When**: Overview/introduction to a topic
**Examples**:
- `AGENTIC-DEVELOPMENT-GUIDE.md`
- `DESIGN-SYSTEM-GUIDE.md`
- `TESTING-GUIDE.md`

---

### Pattern 2: [AGENT]-[PURPOSE]-INSTRUCTIONS.md
**When**: Step-by-step instructions for specific agent
**Examples**:
- `FREYA-WORKFLOW-INSTRUCTIONS.md`
- `SAGA-ANALYSIS-INSTRUCTIONS.md`
- `IDUNN-HANDOFF-INSTRUCTIONS.md`

---

### Pattern 3: [PURPOSE]-TEMPLATE.[ext]
**When**: Reusable template files
**Examples**:
- `work-file-template.yaml`
- `story-file-template.md`
- `page-template.html`
- `demo-data-template.json`

---

### Pattern 4: [SPECIFIC-TOPIC].md
**When**: Documentation for specific feature/concept
**Examples**:
- `PROTOTYPE-ROADMAP.md`
- `SYSTEM-GUIDE.md`
- `FILE-INDEX.md`
- `PROTOTYPE-ANALYSIS.md`

---

### Pattern 5: [function]-[purpose].md
**When**: Instruction files for specific workflows
**Examples**:
- `project-analysis-router.md`
- `outline-based-analysis.md`
- `strategy-work.md`
- `design-work.md`

---

## 🗂️ Folder Organization

### Documentation Folders Should Contain:

```
workflow-folder/
├── [TOPIC]-GUIDE.md                 ← Main entry point
├── [AGENT]-INSTRUCTIONS.md          ← Agent-specific steps
├── [SPECIFIC-TOPIC].md              ← Supporting docs
├── templates/
│   ├── [name]-template.[ext]
│   └── ...
└── examples/
    └── ...
```

**NOT**:
```
workflow-folder/
├── README.md                        ← ❌ Too generic
├── README-2.md                      ← ❌ Even worse!
├── INSTRUCTIONS.md                  ← ❌ Instructions for what?
└── GUIDE.md                         ← ❌ Guide for what?
```

---

## 💡 Benefits of Specific Naming

| Benefit | Description |
|---------|-------------|
| **Self-documenting** | File name tells you what it contains |
| **No confusion** | Can't mistake one file for another |
| **Easy search** | Find exact file you need |
| **Better IDE** | File tabs show meaningful names |
| **Team clarity** | Everyone knows what's what |
| **Future-proof** | Scales to 100+ files without confusion |

---

## 🎯 Examples in WDS

### Good (Current WDS Structure)

```
project-analysis/
├── instructions.md                  ← Entry point (clear function)
├── project-analysis-router.md       ← Router (specific purpose)
├── SYSTEM-GUIDE.md                  ← System overview (specific)
├── analysis-types/
│   ├── outline-based-analysis.md
│   ├── folder-based-analysis.md
│   └── empty-project-response.md
└── work-types/
    ├── strategy-work.md
    └── design-work.md
```

### Bad (Old Pattern - Don't Do This)

```
project-analysis/
├── README.md                        ← ❌ Which readme?
├── instructions.md
├── GUIDE.md                         ← ❌ Guide for what?
├── analysis-types/
│   ├── README.md                    ← ❌ Another readme!
│   └── instructions.md              ← ❌ Confusing
└── work-types/
    └── README.md                    ← ❌ Yet another readme!
```

---

## 🚀 Action Items for Agents

### When Creating New Documentation

**Before creating file, ask**:
1. What is the specific purpose of this file?
2. Is there already a file with this name nearby?
3. Can I make the name more descriptive?

**Then name it**: `[SPECIFIC-TOPIC]-[TYPE].md`

---

### When You See Generic Names

**If you encounter**:
- `README.md` without clear context
- Multiple `README.md` files in related folders
- `INSTRUCTIONS.md` without specificity

**Recommend renaming** to more specific names and document the change.

---

## 📝 File Type Suffixes

**Use these suffixes for clarity**:

- `-GUIDE.md` - Comprehensive overview/introduction
- `-INSTRUCTIONS.md` - Step-by-step how-to
- `-TEMPLATE.[ext]` - Reusable template
- `-ANALYSIS.md` - Analysis/research document
- `-REFERENCE.md` - Quick reference/cheat sheet
- `-INDEX.md` - Index/directory of files
- `-ROADMAP.md` - Status/plan tracking

**Examples**:
- `AGENTIC-DEVELOPMENT-GUIDE.md`
- `FREYA-WORKFLOW-INSTRUCTIONS.md`
- `page-template.html`
- `PROTOTYPE-ANALYSIS.md`
- `TAILWIND-REFERENCE.md`
- `FILE-INDEX.md`
- `PROTOTYPE-ROADMAP.md`

---

## ✅ Checklist: Good File Name?

- [ ] Is it specific (not generic)?
- [ ] Does it describe the content?
- [ ] Is it unique in its folder?
- [ ] Would a new team member understand it?
- [ ] Does it include topic + type?

**If all YES → Good name!**
**If any NO → Make more specific!**

---

## 🎓 Examples

### Generic → Specific

| ❌ Generic | ✅ Specific |
|-----------|------------|
| `README.md` | `AGENTIC-DEVELOPMENT-GUIDE.md` |
| `INSTRUCTIONS.md` | `FREYA-WORKFLOW-INSTRUCTIONS.md` |
| `GUIDE.md` | `DESIGN-SYSTEM-GUIDE.md` |
| `template.yaml` | `work-file-template.yaml` |
| `example.json` | `demo-data-template.json` |

---

## 📊 Impact

**Before (Generic Naming)**:
```
project/
├── README.md                        ← Which one to read?
├── folder1/
│   └── README.md                    ← Too many READMEs!
├── folder2/
│   ├── README.md                    ← Confusing!
│   └── INSTRUCTIONS.md              ← Instructions for what?
└── folder3/
    └── README.md                    ← Stop!
```

**After (Specific Naming)**:
```
project/
├── PROJECT-OVERVIEW-GUIDE.md        ← Clear!
├── folder1/
│   └── FEATURE-X-GUIDE.md           ← Specific!
├── folder2/
│   ├── AGENT-Y-INSTRUCTIONS.md      ← Clear purpose!
│   └── WORKFLOW-Z-INSTRUCTIONS.md   ← Specific!
└── folder3/
    └── COMPONENT-W-GUIDE.md         ← Self-documenting!
```

---

## 🎯 Apply This Rule Everywhere

**WDS Projects**:
- ✅ Use specific names
- ✅ Include topic in name
- ✅ Include type suffix
- ✅ Make self-documenting

**Agent Behavior**:
- ✅ Never create generic `README.md`
- ✅ Always use specific names
- ✅ Recommend renaming when you see generic names
- ✅ Update references when renaming

---

**Consistency creates clarity. Specific names eliminate confusion.** 📚
