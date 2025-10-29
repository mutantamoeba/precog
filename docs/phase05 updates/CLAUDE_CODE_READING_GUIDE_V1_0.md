# Claude Code Reading Guide for Phase 0.5

**Version:** 1.0  
**Date:** 2025-10-21  
**Purpose:** Efficient reading order for Phase 0.5 implementation  
**Estimated Reading Time:** 2-3 hours total

---

## Quick Start

**Your Mission:** Update documentation and YAML files to incorporate Session 7 position monitoring & exit management designs, plus new user customization strategy.

**Time Estimate:** 8-11 hours of work after reading

**Reading Strategy:** Start with master handoff, then dive into specific areas as needed

---

## Reading Order

### Phase 1: Core Context (45 minutes - READ THOROUGHLY)

Read these in order to understand what you're doing and why:

#### 1. PHASE_0_5_COMPREHENSIVE_HANDOFF_V1_0.md (20 min)
**Priority:** 🔴 CRITICAL - START HERE

**What it is:** Your master implementation guide

**What you'll learn:**
- Complete task list for Phase 0.5
- YAML updates required (position_management.yaml)
- Documentation updates required (4 major docs)
- Implementation priorities (Critical → Low)
- Week-by-week execution plan
- Success criteria

**How to read:** 
- Read Parts 1-6 thoroughly (task specifications)
- Skim Parts 7-13 (context and background)
- Bookmark Parts 1-3 for constant reference during implementation

**Key sections to bookmark:**
- Part 1: YAML Configuration Updates (your exact changes)
- Part 3: Documentation Updates (your task list)
- Part 6: Implementation Priorities (your roadmap)

---

#### 2. YAML_CONSISTENCY_AUDIT_V1_0.md (10 min)
**Priority:** 🔴 CRITICAL

**What it is:** Analysis of what's wrong with current YAMLs

**What you'll learn:**
- Exactly what's missing from position_management.yaml
- What needs to be added/updated/removed
- Why these changes are necessary
- Validation checklist

**How to read:**
- Read "Executive Summary" (page 1)
- Read "Section 3: position_management.yaml" thoroughly
- Skim other YAML sections for context
- Use "Validation Checklist" during implementation

**Why you need this:** 
The master handoff tells you WHAT to do; this tells you WHY and shows the current state vs. target state.

---

#### 3. ADR_021_METHOD_ABSTRACTION.md (10 min)
**Priority:** 🟠 HIGH

**What it is:** Architecture decision for Method abstraction layer

**What you'll learn:**
- How configuration bundling will work in Phase 4-5
- Why user customization strategy is designed the way it is
- Database schema for methods table
- Integration with position management

**How to read:**
- Read "Context" and "Decision" sections (pages 1-2)
- Read "Architecture Design" section (database schema)
- Skim "Implementation" sections for future understanding

**Why you need this:**
Multiple documentation updates reference "Methods" and you need to understand this architecture to document it correctly.

---

#### 4. USER_CUSTOMIZATION_STRATEGY_V1_0.md (5 min)
**Priority:** 🟠 HIGH

**What it is:** Complete strategy for user customization across all phases

**What you'll learn:**
- Phase 1: YAML editing (current)
- Phase 1.5: Database overrides (planned)
- Phase 4-5: Method templates (planned)
- Complete list of user-customizable parameters
- Safety constraints (what's NOT customizable)

**How to read:**
- Read "Evolution Across Phases" section (pages 1-5)
- Read "User-Customizable Parameters" section (pages 6-10)
- Read "Safety Constraints" section (page 11)
- Bookmark for reference during CONFIGURATION_GUIDE updates

**Why you need this:**
You'll be documenting user customization in CONFIGURATION_GUIDE_V3.1, so you need to understand the complete strategy.

---

### Phase 2: Detailed Specifications (30 minutes - SKIM THEN REFERENCE)

These provide detailed context. Don't read cover-to-cover now - skim for overview, then reference during specific tasks:

#### 5. CONFIGURATION_GUIDE_UPDATE_SPEC_V1_0.md (15 min)
**Priority:** 🟠 HIGH

**What it is:** Step-by-step specification for updating CONFIGURATION_GUIDE

**What you'll learn:**
- Exact sections to add (7 new sections with full content)
- Exact sections to update (3 existing sections)
- What to remove (edge_reversal references)
- Implementation checklist
- Validation criteria

**How to read NOW:**
- Read "Executive Summary" (page 1)
- Skim "Required Updates" sections to understand scope
- Note the 6-hour time estimate

**How to use DURING implementation:**
- Follow as step-by-step guide when updating CONFIGURATION_GUIDE
- Copy/paste section templates
- Use implementation checklist to track progress

---

#### 6. ADR_020_DEFERRED_EXECUTION.md (5 min)
**Priority:** 🟡 MEDIUM

**What it is:** Decision to defer Dynamic Depth Walker to Phase 8

**What you'll learn:**
- Why Phase 5 uses simple execution only
- What metrics would trigger Phase 8 implementation
- How this affects documentation

**How to read:**
- Read "Context" and "Decision" sections
- Skim implementation details

**Why you need this:**
Documentation should clarify that Phase 5 uses simple execution, with advanced execution deferred to Phase 8.

---

#### 7. CLAUDE_CODE_HANDOFF_UPDATED_V1_0.md (10 min)
**Priority:** 🟡 MEDIUM

**What it is:** Original Session 7 handoff before my enhancements

**What you'll learn:**
- Original task list from Session 7
- Database schema details
- Exit condition specifications

**How to read:**
- Skim "New Deliverables" section (pages 1-3)
- Skim "Configuration Updates Needed" (pages 4-6)
- Reference "Files to Update" section as needed

**Why you need this:**
Provides additional context and details that complement the master handoff. Use as secondary reference.

---

### Phase 3: Implementation Specs (45 minutes - REFERENCE ONLY)

These are detailed specifications for Phase 5 CODE implementation. For Phase 0.5 DOCUMENTATION work, you only need to reference these when writing docs:

#### 8. PHASE_5_POSITION_MONITORING_SPEC_V1_0.md (15 min)
**Priority:** 🟢 LOW (for Phase 0.5)

**What it is:** Detailed specification for PositionMonitor class and monitoring system

**When to read:**
- When documenting monitoring in CONFIGURATION_GUIDE
- When updating MASTER_REQUIREMENTS monitoring sections
- When you need to understand monitoring algorithms

**How to use:**
- Don't read cover-to-cover now
- Reference specific sections as needed:
  - "Monitoring Frequency" when documenting monitoring
  - "API Rate Management" when documenting rate limits
  - "Class Implementation" when validating requirements

---

#### 9. PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md (15 min)
**Priority:** 🟢 LOW (for Phase 0.5)

**What it is:** Detailed specification for exit condition evaluation and execution

**When to read:**
- When documenting exit priorities in CONFIGURATION_GUIDE
- When updating MASTER_REQUIREMENTS exit sections
- When you need to understand exit algorithms

**How to use:**
- Reference "Exit Priority Hierarchy" section
- Reference "Execution Strategies" section
- Use "Exit Condition Details" when documenting each condition

---

#### 10. PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md (15 min)
**Priority:** 🟢 LOW (for Phase 0.5)

**What it is:** Complete architecture overview with diagrams

**When to read:**
- When you need big-picture understanding
- When documenting system architecture
- When validating component interactions

**How to use:**
- Reference flow diagrams when documenting processes
- Use for understanding how components fit together
- Good for sanity checks during documentation

---

### Phase 4: Optional Context (Skip Unless Needed)

These provide additional background but aren't necessary for Phase 0.5 work:

#### 11. ORDER_EXECUTION_ARCHITECTURE_ASSESSMENT_V1_0.md
**Priority:** ⚪ OPTIONAL

**What it is:** Analysis of Grok's Dynamic Depth Walker recommendation

**When to read:** Only if you want to understand why we're not implementing advanced execution in Phase 5

**How to use:** Background context only

---

#### 12. PHASE_8_ADVANCED_EXECUTION_SPEC.md
**Priority:** ⚪ OPTIONAL

**What it is:** Specification for future Phase 8 advanced execution

**When to read:** Not needed for Phase 0.5 work

**How to use:** Reference if documenting Phase 8 plans

---

## Reading Time Breakdown

| Phase | Documents | Time | Priority |
|-------|-----------|------|----------|
| Phase 1: Core Context | 4 docs | 45 min | 🔴 Must Read |
| Phase 2: Detailed Specs | 3 docs | 30 min | 🟠 Skim & Reference |
| Phase 3: Implementation Specs | 3 docs | 45 min | 🟢 Reference Only |
| Phase 4: Optional Context | 2 docs | 30 min | ⚪ Skip Unless Needed |

**Total Essential Reading:** 1 hour 15 minutes (Phase 1 + Phase 2)  
**Total Reference Material:** 45 minutes (Phase 3)  
**Total Optional:** 30 minutes (Phase 4)

---

## Reading Strategy by Task

### Task: Update position_management.yaml

**Must Read:**
1. PHASE_0_5_COMPREHENSIVE_HANDOFF (Part 1)
2. YAML_CONSISTENCY_AUDIT (Section 3)

**Reference:**
- PHASE_5_POSITION_MONITORING_SPEC (monitoring section)
- PHASE_5_EXIT_EVALUATION_SPEC (exit priorities)

---

### Task: Update MASTER_REQUIREMENTS

**Must Read:**
1. PHASE_0_5_COMPREHENSIVE_HANDOFF (Part 3, item 1)
2. YAML_CONSISTENCY_AUDIT (for understanding changes)

**Reference:**
- PHASE_5_POSITION_MONITORING_SPEC (for REQ-MON-* requirements)
- PHASE_5_EXIT_EVALUATION_SPEC (for REQ-EXIT-* requirements)
- ADR_020 (for execution requirements)

---

### Task: Update DATABASE_SCHEMA_SUMMARY

**Must Read:**
1. PHASE_0_5_COMPREHENSIVE_HANDOFF (Part 2)
2. CLAUDE_CODE_HANDOFF_UPDATED (database sections)

**Reference:**
- PHASE_5_POSITION_MONITORING_SPEC (position table updates)
- PHASE_5_EXIT_EVALUATION_SPEC (new tables)

---

### Task: Update CONFIGURATION_GUIDE

**Must Read:**
1. PHASE_0_5_COMPREHENSIVE_HANDOFF (Part 3, item 3)
2. CONFIGURATION_GUIDE_UPDATE_SPEC (entire document)
3. USER_CUSTOMIZATION_STRATEGY (entire document)
4. ADR_021 (architecture context)

**Reference:**
- PHASE_5_POSITION_MONITORING_SPEC (when documenting monitoring)
- PHASE_5_EXIT_EVALUATION_SPEC (when documenting exits)
- ADR_020 (when documenting execution)

---

### Task: Update DEVELOPMENT_PHASES

**Must Read:**
1. PHASE_0_5_COMPREHENSIVE_HANDOFF (Part 3, item 4)

**Reference:**
- PHASE_5_POSITION_MONITORING_SPEC (Phase 5a scope)
- PHASE_5_EXIT_EVALUATION_SPEC (Phase 5a scope)
- PHASE_5_EVENT_LOOP_ARCHITECTURE (Phase 5 overview)

---

## Key Concepts to Understand

After reading Phase 1 documents, you should understand:

✅ **Dynamic Monitoring Frequency**
- 30s normal, 5s urgent
- Urgent triggers: within 2% of thresholds
- API rate management via caching

✅ **Exit Priority Hierarchy**
- CRITICAL > HIGH > MEDIUM > LOW
- 10 exit conditions (edge_reversal removed)
- Multiple triggers resolve to highest priority

✅ **Urgency-Based Execution**
- CRITICAL: Market orders, immediate
- HIGH: Aggressive limits, walk 2x then market
- MEDIUM: Fair limits, walk 5x
- LOW: Conservative limits, walk 10x

✅ **Partial Exits**
- Stage 1: 50% at +15% profit
- Stage 2: 25% at +25% profit
- Remaining 25% rides with trailing stop

✅ **User Customization Evolution**
- Phase 1: YAML editing (current)
- Phase 1.5: Database overrides (planned)
- Phase 4-5: Method templates (planned)

✅ **Method Abstraction (ADR-021)**
- Bundles: Strategy + Model + Position + Risk + Execution
- Immutable versions
- Per-method enable/disable of rules
- A/B testing capability

✅ **Safety Constraints**
- Circuit breakers NOT customizable
- API limits NOT customizable
- CRITICAL exits NOT customizable
- stop_loss/circuit_breaker always enabled

---

## Quick Reference During Implementation

### Where to Find Exact YAML Changes

**Location:** PHASE_0_5_COMPREHENSIVE_HANDOFF_V1_0.md, Part 1

**Sections to copy:**
1. Monitoring section (lines 50-66)
2. Exit priorities section (lines 164-179)
3. Exit execution section (lines 183-207)
4. Partial exits update (lines 210-223)
5. Liquidity section (lines 220-226)
6. Remove edge_reversal (lines 396-405)

### Where to Find Exact Database Changes

**Location:** PHASE_0_5_COMPREHENSIVE_HANDOFF_V1_0.md, Part 2

**SQL to run:**
- Position table updates (lines 10-23)
- position_exits table (lines 33-48)
- exit_attempts table (lines 51-63)

### Where to Find Documentation Task List

**Location:** PHASE_0_5_COMPREHENSIVE_HANDOFF_V1_0.md, Part 3

**Updates required:**
1. MASTER_REQUIREMENTS V2.4 → V2.5 (lines 9-25)
2. DATABASE_SCHEMA_SUMMARY V1.4 → V1.5 (lines 29-32)
3. CONFIGURATION_GUIDE V3.0 → V3.1 (lines 36-38)
4. DEVELOPMENT_PHASES V1.2 → V1.3 (lines 42-47)

### Where to Find Implementation Checklist

**Location:** PHASE_0_5_COMPREHENSIVE_HANDOFF_V1_0.md, Part 6

**Priorities:**
- Priority 1: CRITICAL (lines 4-11)
- Priority 2: HIGH (lines 15-22)
- Priority 3: MEDIUM (lines 26-33)
- Priority 4: LOW (lines 37-43)

---

## Validation Checklist

After completing Phase 0.5 work, verify you've addressed everything:

### YAML Updates
- [ ] position_management.yaml has monitoring section
- [ ] position_management.yaml has exit_priorities section
- [ ] position_management.yaml has exit_execution section
- [ ] position_management.yaml has 2nd partial exit stage
- [ ] position_management.yaml has liquidity section
- [ ] edge_reversal removed (if present)
- [ ] YAML validates without errors

### Database Updates
- [ ] positions table has monitoring fields
- [ ] positions table has trailing stop fields
- [ ] positions table has exit tracking fields
- [ ] position_exits table created
- [ ] exit_attempts table created
- [ ] All indexes created
- [ ] Schema validates without errors

### Documentation Updates
- [ ] MASTER_REQUIREMENTS V2.5 has REQ-MON-* requirements
- [ ] MASTER_REQUIREMENTS V2.5 has REQ-EXIT-* requirements
- [ ] DATABASE_SCHEMA_SUMMARY V1.5 documents new fields/tables
- [ ] CONFIGURATION_GUIDE V3.1 has 7 new sections
- [ ] CONFIGURATION_GUIDE V3.1 has updated sections
- [ ] CONFIGURATION_GUIDE V3.1 has no edge_reversal references
- [ ] DEVELOPMENT_PHASES V1.3 has expanded Phase 5a
- [ ] MASTER_INDEX V2.3 references all new/updated docs
- [ ] All cross-references work

### Consistency Checks
- [ ] Run YAML validation tool
- [ ] Run consistency audit tool
- [ ] All parameters align across files
- [ ] No broken references
- [ ] No deprecated features mentioned

---

## Troubleshooting

### "I don't understand the Method abstraction"

**Read:** ADR_021_METHOD_ABSTRACTION.md (Context + Decision sections)

**Key Point:** Methods bundle complete configurations (strategy + model + position mgmt + risk + execution) as reusable templates that can be cloned, customized, and A/B tested.

---

### "I don't know what to write in CONFIGURATION_GUIDE"

**Read:** CONFIGURATION_GUIDE_UPDATE_SPEC_V1_0.md

**Key Point:** This document provides exact content for each new section. Follow it step-by-step.

---

### "I'm confused about user customization phases"

**Read:** USER_CUSTOMIZATION_STRATEGY_V1_0.md (Evolution Across Phases section)

**Key Point:** 
- Phase 1 = YAML editing
- Phase 1.5 = Database overrides
- Phase 4-5 = Method templates
Each builds on the previous.

---

### "I don't understand why we removed edge_reversal"

**Read:** YAML_CONSISTENCY_AUDIT_V1_0.md (Section 3) and PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md

**Key Point:** edge_reversal is redundant. All scenarios are covered by:
- early_exit (edge drops below 2%)
- edge_disappeared (edge turns negative)
- stop_loss (losses exceed threshold)

---

### "Which parameters are user-customizable?"

**Read:** USER_CUSTOMIZATION_STRATEGY_V1_0.md (Complete List section)

**Key Point:** Look for `# user-customizable` annotations in YAML. Safety-critical parameters (circuit breakers, API limits, CRITICAL exits) are NEVER customizable.

---

## Time Management

### Hour 1: Reading Core Context
- PHASE_0_5_COMPREHENSIVE_HANDOFF (20 min)
- YAML_CONSISTENCY_AUDIT (10 min)
- ADR_021_METHOD_ABSTRACTION (10 min)
- USER_CUSTOMIZATION_STRATEGY (5 min)
- CONFIGURATION_GUIDE_UPDATE_SPEC (15 min)

### Hour 2: YAML Updates
- Update position_management.yaml (1 hour)
- Validate YAML
- Commit

### Hour 3-4: Critical Documentation
- MASTER_REQUIREMENTS V2.5 (1 hour)
- DATABASE_SCHEMA_SUMMARY V1.5 (1 hour)
- Review and commit

### Hour 5-8: Major Documentation
- CONFIGURATION_GUIDE V3.1 (4 hours)
  - Follow CONFIGURATION_GUIDE_UPDATE_SPEC step-by-step
  - Reference other docs as needed

### Hour 9-10: Remaining Documentation
- DEVELOPMENT_PHASES V1.3 (30 min)
- MASTER_INDEX V2.3 (30 min)
- Review and commit

### Hour 11: Database & Validation
- Apply database schema updates (30 min)
- Run validation tools (30 min)
- Final review

**Total: 11 hours**

---

## Summary

**Start with:** PHASE_0_5_COMPREHENSIVE_HANDOFF_V1_0.md (your master guide)

**Core reading:** 4 documents, 45 minutes

**Reference as needed:** 3 documents, 30 minutes

**Total essential time:** 1 hour 15 minutes

**Then execute:** 8-11 hours of implementation work

**Result:** Phase 0.5 complete, ready for Phase 5 implementation

---

## Contact Points

If you get stuck during Phase 0.5 work:

1. **Check the troubleshooting section above**
2. **Re-read the relevant section in PHASE_0_5_COMPREHENSIVE_HANDOFF**
3. **Reference the detailed specs (Phase 3 documents)**
4. **Flag for user review if architectural decision needed**

---

**Good luck with Phase 0.5! The reading is front-loaded, but it makes the implementation much smoother.**

**Remember:** You're updating documentation and YAMLs to incorporate designs from Session 7 + new user customization strategy. The actual Phase 5 code implementation comes later.

🚀 **You've got this!**

---

**Document:** CLAUDE_CODE_READING_GUIDE_V1_0.md  
**Created:** 2025-10-21  
**Purpose:** Efficient reading guide for Phase 0.5 implementation  
**Status:** ✅ Complete
