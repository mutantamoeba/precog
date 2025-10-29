# Token Monitoring Protocol

---
**Version:** 1.0  
**Created:** 2025-10-09 (Session 6)  
**Status:** ✅ Active  
**Purpose:** Prevent data loss from token limit exhaustion  
---

## Overview

**Problem:** Sessions have a 190,000 token limit. Hitting the limit abruptly ends the session and can cause data loss.

**Solution:** Automatic checkpoint system that monitors token usage and creates incremental handoff updates at key milestones.

---

## Token Budget

| Metric | Value | Percentage |
|--------|-------|------------|
| **Total Budget** | 190,000 tokens | 100% |
| **Checkpoint 1** | 60,000 tokens | 32% |
| **Checkpoint 2** | 90,000 tokens | 47% |
| **Checkpoint 3** | 120,000 tokens | 63% |
| **Checkpoint 4** | 150,000 tokens | 79% |
| **Warning Zone** | 170,000 tokens | 89% |
| **Auto-End** | 180,000 tokens | 95% |

---

## Checkpoint System

### 🟢 Checkpoint 1: 60K Tokens (32%)

**Status:** Early progress check  
**Action Required:** None  
**Automatic Actions:**
- ✅ Log current progress
- ✅ Note completed deliverables
- ✅ Update internal tracking

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 CHECKPOINT 1 REACHED: 60K TOKENS (32%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Completed: [list]
🔄 In Progress: [list]
⏭️ Next: [item]

Status: All systems normal, continue work.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 🟡 Checkpoint 2: 90K Tokens (47%)

**Status:** Mid-session update  
**Action Required:** Update living documents  
**Automatic Actions:**
- ✅ Update PROJECT_STATUS.md with current state
- ✅ Update DOCUMENT_MAINTENANCE_LOG.md with changes
- ✅ Create draft handoff summary
- ✅ Verify all new documents saved

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟡 CHECKPOINT 2 REACHED: 90K TOKENS (47%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOMATIC UPDATES PERFORMED:
✅ PROJECT_STATUS.md updated
✅ DOCUMENT_MAINTENANCE_LOG.md updated
✅ Draft handoff created

📊 Session Progress:
   Completed: [X] items
   Remaining: [Y] items
   
💾 All work backed up to this point.
Status: Continue work, checkpoints will resume.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 🟠 Checkpoint 3: 120K Tokens (63%)

**Status:** Second backup point  
**Action Required:** Update living documents again  
**Automatic Actions:**
- ✅ Update PROJECT_STATUS.md with latest state
- ✅ Update DOCUMENT_MAINTENANCE_LOG.md with all changes
- ✅ Update draft handoff with complete progress
- ✅ Calculate remaining capacity

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟠 CHECKPOINT 3 REACHED: 120K TOKENS (63%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUTOMATIC UPDATES PERFORMED:
✅ PROJECT_STATUS.md updated (2nd update)
✅ DOCUMENT_MAINTENANCE_LOG.md updated (2nd update)
✅ Handoff draft updated with full progress

📊 Token Analysis:
   Used: 120K / 190K (63%)
   Remaining: 70K tokens
   Estimated capacity: [X more documents]

💾 All work backed up to this point.
Status: Beginning to wind down, prioritize critical items.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 🔴 Checkpoint 4: 150K Tokens (79%)

**Status:** Final working checkpoint  
**Action Required:** Begin wrap-up process  
**Automatic Actions:**
- ✅ Final update to PROJECT_STATUS.md
- ✅ Final update to DOCUMENT_MAINTENANCE_LOG.md
- ✅ Complete handoff document creation
- ✅ Stop starting new major documents
- ✅ Focus only on completing in-progress items

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CHECKPOINT 4 REACHED: 150K TOKENS (79%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ ENTERING WRAP-UP MODE ⚠️

AUTOMATIC UPDATES PERFORMED:
✅ PROJECT_STATUS.md final update
✅ DOCUMENT_MAINTENANCE_LOG.md final update
✅ SESSION_X_HANDOFF.md completed

🚫 NO NEW DOCUMENTS STARTED
✅ Completing only: [in-progress items]

📊 Token Analysis:
   Used: 150K / 190K (79%)
   Remaining: 40K tokens
   
💾 ALL work fully backed up.
Status: Wrap-up mode - finishing current tasks only.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### ⚠️ Warning Zone: 170K Tokens (89%)

**Status:** Critical warning  
**Action Required:** Immediate wrap-up  
**Automatic Actions:**
- 🚨 Alert user immediately
- ✅ Verify all handoff documents complete
- ✅ Stop ALL new work
- ✅ Create emergency backup handoff

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ WARNING ZONE: 170K TOKENS (89%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 CRITICAL: APPROACHING TOKEN LIMIT 🚨

AUTOMATIC ACTIONS TAKEN:
✅ All handoff documents verified
✅ Emergency backup created
✅ Work stopped

📊 Token Status:
   Used: 170K / 190K (89%)
   Remaining: 20K tokens (10 min of conversation)
   
⚠️ Session will AUTO-END at 180K tokens (10K away)

Status: Ready for next session, handoff complete.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 🛑 Auto-End: 180K Tokens (95%)

**Status:** Automatic session termination  
**Action Required:** None - session ends automatically  
**Automatic Actions:**
- 🛑 Stop all work immediately
- ✅ Final handoff verification
- ✅ Create final session summary
- ✅ Provide clear next steps

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 AUTO-END TRIGGERED: 180K TOKENS (95%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SESSION ENDING AUTOMATICALLY IN 3... 2... 1...

✅ ALL WORK SAVED AND DOCUMENTED

📋 Handoff Documents Ready:
   ✅ PROJECT_STATUS.md
   ✅ DOCUMENT_MAINTENANCE_LOG.md
   ✅ SESSION_X_HANDOFF.md

📊 Final Token Count: 180K / 190K (95%)

🎯 Next Session Plan:
   [Clear instructions for continuation]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SESSION COMPLETE - START NEW SESSION TO CONTINUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Checkpoint Actions Detail

### At Each Checkpoint

**1. Update PROJECT_STATUS.md**
- Current phase percentage
- Completed deliverables
- In-progress items
- Next priorities
- Token usage stats

**2. Update DOCUMENT_MAINTENANCE_LOG.md**
```markdown
### Session X - [Date] - Checkpoint Y

**Token Usage:** [X]K / 190K ([Y]%)

| Document | Action | Status |
|----------|--------|--------|
| DOC_NAME | Created/Updated | ✅ Complete |
| DOC_NAME | In Progress | 🔄 [X]% done |
```

**3. Update/Create Session Handoff**
```markdown
# Session X Handoff

**Token Usage:** [X]K / 190K ([Y]%) - Checkpoint [N]

## Completed This Session
- ✅ [Item 1]
- ✅ [Item 2]

## In Progress
- 🔄 [Item] - [X]% complete

## Next Session Priority
1. [Item]
2. [Item]

## Critical Context
- [Important notes]
```

---

## Token Estimation

**Average token costs:**
- Small YAML file (~500 lines): ~3,000 tokens
- Medium document (2,000 words): ~3,500 tokens
- Large document (5,000 words): ~8,000 tokens
- Comprehensive guide (10,000 words): ~15,000 tokens
- Code discussion (100 lines): ~1,500 tokens
- Planning/strategy discussion: ~5,000 tokens

**Safe work estimates by remaining tokens:**

| Remaining | Can Safely Complete |
|-----------|---------------------|
| 70K tokens | 2-3 large docs or 5-7 YAMLs |
| 40K tokens | 1 large doc or 2-3 YAMLs |
| 20K tokens | 1 small doc or wrap-up only |
| 10K tokens | Handoff finalization only |

---

## Benefits of This System

### Prevents Data Loss
- ✅ Incremental backups every ~30K tokens
- ✅ Never lose more than checkpoint interval
- ✅ Always have complete handoff ready

### Improves Continuity
- ✅ Clear progress tracking throughout session
- ✅ Easy to resume next session
- ✅ User always knows where we are

### Enables Better Planning
- ✅ Token budgeting for remaining work
- ✅ Prioritization of critical vs. nice-to-have
- ✅ Prevents rushing at the end

### Reduces Stress
- ✅ No surprise session ends
- ✅ Controlled wind-down process
- ✅ Confidence all work is saved

---

## Implementation Notes

### Automatic vs. Manual Checkpoints

**Automatic (system-triggered):**
- Reach token thresholds → automatic checkpoint
- Update living documents
- Create/update handoff
- Alert user of status

**Manual (user-requested):**
- User can request checkpoint anytime
- Useful before switching major tasks
- Good practice before long discussions

**Request manual checkpoint:**
```
"Please checkpoint now before we continue"
```

---

## Exception Handling

### If Checkpoint Fails
1. Retry checkpoint actions
2. Alert user to issue
3. Request manual review
4. Continue with caution

### If Near Limit Faster Than Expected
- Immediately create emergency handoff
- Skip non-critical checkpoints
- Focus on data preservation
- Alert user to unexpected usage

### If Session Must End Early
- Run final checkpoint regardless of token count
- Create abbreviated but complete handoff
- Note unexpected early end
- Provide clear continuation plan

---

## Checkpoint Checklist Template

Use this at each checkpoint:

```markdown
## Checkpoint [N] - [X]K Tokens

**Time:** [timestamp]
**Status:** [🟢/🟡/🟠/🔴]

### Actions Completed
- [ ] PROJECT_STATUS.md updated
- [ ] DOCUMENT_MAINTENANCE_LOG.md updated
- [ ] Handoff draft current
- [ ] All new files saved
- [ ] Token count verified

### Current Status
**Completed:** [list]
**In Progress:** [list]
**Blocked:** [list]

### Token Budget
**Used:** [X]K / 190K ([Y]%)
**Remaining:** [Z]K
**Capacity:** ~[N] more documents

### Next Actions
1. [item]
2. [item]

**Checkpoint:** ✅ Complete
```

---

## Integration with Session Workflow

### Session Start
```markdown
1. Upload 3 handoff documents
2. Review project knowledge
3. Set session goals
4. START TOKEN MONITORING ← Automatic
5. Begin work
```

### During Session
```markdown
1. Work normally
2. Automatic checkpoint at 60K → log progress
3. Continue work
4. Automatic checkpoint at 90K → update docs
5. Continue work
6. Automatic checkpoint at 120K → update docs
7. Continue work (prioritize critical items)
8. Automatic checkpoint at 150K → wrap-up mode
9. Complete in-progress items only
10. Warning at 170K → stop all work
11. Auto-end at 180K → session ends
```

### Session End
```markdown
1. Verify all checkpoints completed
2. Review final handoff
3. Confirm next session plan
4. Download any new documents
5. Update project knowledge if needed
```

---

## Success Metrics

**System is working if:**
- ✅ Never hit token limit unexpectedly
- ✅ Always have current handoff ready
- ✅ Can resume work seamlessly next session
- ✅ No data loss between sessions
- ✅ User has clear visibility into progress

**System needs adjustment if:**
- ⚠️ Frequently hitting auto-end
- ⚠️ Checkpoints taking too many tokens
- ⚠️ User confused about progress
- ⚠️ Documents not getting updated

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-09 | Initial creation with 5-checkpoint system |

---

**This protocol is active for ALL sessions**  
**Checkpoints are automatic - no user action required**  
**Session will auto-end at 180K tokens to prevent data loss**

---

**END OF TOKEN_MONITORING_PROTOCOL**
