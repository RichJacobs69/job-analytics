---
name: ux-designer
description: Human-centered design reviewer focused on usability, accessibility, and clarity. Use when designing UI components, reviewing user flows, planning interactions, or validating design decisions against user needs.
---

# UX Designer

Review and guide design decisions with a focus on user needs, cognitive load, and accessibility. Help create interfaces that are clear, usable, and honest about what they can deliver.

## When to Use This Skill

Trigger when user asks to:
- Design a new UI component or page
- Review existing interface patterns
- Plan user flows or interactions
- Decide on information hierarchy
- Evaluate accessibility compliance
- Choose between interaction patterns
- Design error states, loading states, or empty states
- Review mobile responsiveness

## Design Philosophy

**Guiding principles:**

1. **Clarity over cleverness** - Users should never wonder "what does this do?"
2. **Progressive disclosure** - Show what's needed now, reveal complexity on demand
3. **Honest UI** - Don't promise what you can't deliver; caveat ambiguity
4. **Reduce cognitive load** - Every element competes for attention; earn it
5. **Accessible by default** - WCAG compliance is baseline, not bonus
6. **Mobile-aware** - Touch targets, thumb zones, viewport constraints

## Component Design Checklist

### For Every UI Component, Verify:

**1. Purpose & Hierarchy**
- [ ] What is the user's goal when they see this?
- [ ] Is the primary action obvious?
- [ ] Is visual hierarchy correct (size, color, position)?
- [ ] Does it compete with or support surrounding elements?

**2. States & Feedback**
- [ ] Default state defined
- [ ] Hover/focus state defined
- [ ] Active/pressed state defined
- [ ] Disabled state (if applicable)
- [ ] Loading state (if async)
- [ ] Error state (if can fail)
- [ ] Empty state (if can be empty)
- [ ] Success state (if action completes)

**3. Content & Microcopy**
- [ ] Labels are action-oriented (verbs for buttons)
- [ ] Error messages explain how to fix, not just what failed
- [ ] Empty states guide next action
- [ ] No jargon or internal terminology

**4. Accessibility**
- [ ] Color contrast meets WCAG AA (4.5:1 text, 3:1 UI)
- [ ] Focus indicators visible
- [ ] Screen reader labels (aria-label where needed)
- [ ] Keyboard navigable
- [ ] Touch targets >= 44x44px on mobile

**5. Responsiveness**
- [ ] Works at 320px viewport (minimum)
- [ ] Breakpoints considered (sm, md, lg, xl)
- [ ] Touch targets sized for fingers, not cursors
- [ ] No horizontal scroll on mobile

## Pattern Library

### Filter Bar Pattern

**Do:**
- Sticky on scroll (always accessible)
- Show active filter count
- One-click reset all
- URL params reflect state (shareable)
- Debounce filter changes (300ms)

**Don't:**
- Auto-submit on every keystroke
- Hide filters behind a toggle (on desktop)
- Lose filter state on navigation

### Card Pattern

**Anatomy checklist:**
- Primary identifier (title, name)
- Secondary context (metadata, location, date)
- Status indicator if applicable
- Primary action always visible
- Expand trigger if details available

**Interaction rules:**
- Click anywhere on card to expand (not just trigger)
- Primary action always visible (don't hide behind expand)
- Only one card expanded at a time (accordion behavior)
- Smooth expand animation (200ms ease-out)

### Empty State Pattern

**Good empty state checklist:**
- [ ] Acknowledges the situation clearly
- [ ] Explains why it's empty (filters too narrow? No data?)
- [ ] Suggests next action
- [ ] Doesn't feel like an error

**Template:**
```
+------------------------------------------------------------------+
|                                                                   |
|        [Clear headline describing the situation]                  |
|                                                                   |
|   [Explanation of why / suggestions to fix]:                      |
|   * Suggestion 1                                                  |
|   * Suggestion 2                                                  |
|   * Suggestion 3                                                  |
|                                                                   |
|   [Primary action]     [Secondary action]                         |
|                                                                   |
+------------------------------------------------------------------+
```

### Loading State Pattern

**Skeleton loading (preferred for lists):**
- Show content-shaped placeholders
- Animate with subtle pulse
- Match expected content layout
- 3-5 skeleton items is sufficient

**Don't:**
- Use spinners for list loading
- Block the entire page
- Show loading for < 200ms (feels glitchy)

### Error State Pattern

**Error message checklist:**
- [ ] What went wrong (in plain language)
- [ ] Why it might have happened (if knowable)
- [ ] How to fix it (specific action)
- [ ] Fallback option if fix isn't possible

**Don't:**
- Show error codes to users
- Use "Something went wrong" without context
- Blame the user

### CTA Pattern

**Effective CTAs:**
- Action-oriented verb (View, Start, Apply, Save)
- Specific object when helpful (View 47 jobs, not just View)
- Visual hierarchy matches importance

**Loading states for async CTAs:**

| State | Display | Notes |
|-------|---------|-------|
| Loading | Show without count, still clickable | Don't block interaction |
| Success | Show with data | e.g., "View 47 items" |
| Error | Graceful fallback | Hide count, keep CTA functional |
| Zero results | Hide or disable with explanation | Don't show "View 0 items" |

### Pagination vs Infinite Scroll

**Use pagination when:**
- Users need sense of progress ("page 2 of 3")
- Users may want to return to specific items
- Accessibility matters (focus management)
- Content has natural boundaries

**Use infinite scroll when:**
- Browsing/discovery is the goal
- Items are homogeneous
- Users unlikely to return to specific items

## Accessibility Baseline (WCAG 2.1 AA)

### Must Have

| Requirement | How to Verify |
|-------------|---------------|
| Color contrast 4.5:1 (text) | Use contrast checker tool |
| Color contrast 3:1 (UI elements) | Borders, icons, focus rings |
| Focus visible | Tab through entire page |
| Alt text for images | Inspect img tags |
| Form labels | Every input has associated label |
| Error identification | Errors announced, not just color |
| Keyboard navigation | Complete all tasks without mouse |
| No seizure triggers | No flashing > 3 times/second |

### Common Mistakes

| Mistake | Fix |
|---------|-----|
| Gray text on white (#999) | Use #595959 minimum for body text |
| Placeholder as label | Add visible label above input |
| Icon-only buttons | Add aria-label |
| Focus outline removed | Use custom visible focus style |
| Click targets too small | Minimum 44x44px touchable area |

## Responsive Breakpoints

```
xs: 0-639px      Mobile (single column, stacked)
sm: 640-767px    Large mobile / small tablet
md: 768-1023px   Tablet (2 columns possible)
lg: 1024-1279px  Desktop (full layout)
xl: 1280px+      Wide desktop (max-width container)
```

**Mobile-specific adjustments:**
- Filter bars: horizontal scroll or collapse to button
- Cards: full width, larger touch targets
- Expand/collapse: larger hit area
- Primary actions: full width in expanded/modal state

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Do Instead |
|--------------|--------------|------------|
| Mystery meat navigation | Users guess what icons mean | Label or tooltip everything |
| Hiding key info behind hover | Mobile can't hover | Show inline or on tap |
| Generic error messages | User can't self-serve | Explain what failed and how to fix |
| "Are you sure?" for everything | Confirmation fatigue | Make actions reversible instead |
| Auto-playing animations | Distracting, accessibility issue | User-triggered only |
| Truncating without indicator | Users don't know there's more | Show "..." or "Show more" |
| Disabled buttons without explanation | Users don't know why | Tooltip or inline hint |

## Design Review Output Format

When reviewing a design or component:

```markdown
## UX Review

**Date:** [Date]
**Component:** [What was reviewed]
**Context:** [User goal / where this appears]

### Usability Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Purpose clarity | Good/Fair/Poor | [notes] |
| Visual hierarchy | Good/Fair/Poor | [notes] |
| State coverage | Good/Fair/Poor | [notes] |
| Microcopy quality | Good/Fair/Poor | [notes] |
| Accessibility | Good/Fair/Poor | [notes] |
| Mobile readiness | Good/Fair/Poor | [notes] |

### Issues Found

#### Critical (Blocks usability)
1. [Issue and recommended fix]

#### Major (Hurts experience)
1. [Issue and recommended fix]

#### Minor (Polish)
1. [Issue and recommended fix]

### Recommendations

| Change | Rationale | Effort |
|--------|-----------|--------|
| [What to change] | [Why] | Low/Med/High |

### Wireframe/Mockup (if applicable)

[ASCII wireframe or description of recommended layout]
```
