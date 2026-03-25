# Design System Strategy: The Secure Curator

## 1. Overview & Creative North Star
The North Star for this design system is **"The Secure Curator."** In a world of chaotic data and high-stakes privacy, this system acts as a calm, authoritative presence. We are moving away from the "clunky enterprise software" archetype and toward a high-end editorial experience that feels as much like a premium financial journal as it does a security tool.

To achieve this, we break the "standard template" look by utilizing **intentional asymmetry** and **tonal layering**. We replace rigid, 1px-bordered grids with expansive breathing room and sophisticated surface transitions. The interface should feel like stacked sheets of architectural vellum—translucent, precise, and structurally sound.

## 2. Colors & Surface Philosophy
The palette is rooted in deep, authoritative blues (`primary: #001735`) and high-stability neutrals.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to define sections or cards. Hierarchy must be established through:
- **Background Color Shifts:** Use `surface` as your base, placing `surface-container-low` for secondary areas and `surface-container-lowest` (pure white) for high-priority interactive cards.
- **Tonal Transitions:** Define boundaries by the juxtaposition of two different surface tokens (e.g., a side panel in `surface-container` against a workspace in `surface`).

### Surface Hierarchy & Nesting
Treat the UI as a physical stack. The deeper the data (the more "sensitive" the redaction), the higher the elevation token. 
- **Base Layer:** `surface` (#f7fafc)
- **Structural Grouping:** `surface-container` (#ebeef0)
- **Interactive Focal Points:** `surface-container-lowest` (#ffffff)
- **The "Redaction" Accent:** Use `tertiary_container` (#600008) and `on_tertiary_container` (#ff5a56) for high-alert sensitive data. It provides a sophisticated, wine-dark "redaction" look that feels more premium than a standard bright red.

### The "Glass & Gradient" Rule
To elevate the "Smart" aspect of the tool, use **Glassmorphism** for floating toolbars and entity inspectors. 
- **Token:** Use `surface_variant` at 80% opacity with a `24px` backdrop blur.
- **Signature Textures:** Apply a subtle linear gradient from `primary` (#001735) to `primary_container` (#0d2c52) on primary action buttons to give them weight and "visual soul."

## 3. Typography
The system uses a dual-font strategy to balance editorial authority with functional clarity.

*   **Display & Headlines (Manrope):** Chosen for its geometric precision and modern "tech-forward" feel. Use `display-lg` and `headline-md` for page titles and high-level dashboard metrics to establish a "Curated" tone.
*   **Interface & Body (Inter):** The workhorse. Use `body-md` for document text and `label-sm` for technical metadata. Inter’s tall x-height ensures maximum readability when users are scanning dense legal or medical documents for redaction.

**Hierarchy Tip:** Always pair a `headline-sm` (Manrope) with a `label-md` (Inter, uppercase, 0.05em tracking) to create a sophisticated, high-contrast header section.

## 4. Elevation & Depth

### The Layering Principle
Depth is achieved through **Tonal Layering** rather than shadows. 
- Place a `surface-container-lowest` card on a `surface-container-low` section. This creates a soft, natural "lift" that mimics high-quality paper stock.

### Ambient Shadows
Shadows are reserved only for "floating" elements like dropdowns or active entity popovers.
- **Spec:** `0px 12px 32px rgba(24, 28, 30, 0.06)`. 
- The shadow must be a tinted version of the `on-surface` color to ensure it looks like ambient light, not a "drop shadow" effect.

### The "Ghost Border" Fallback
If contrast is legally required for accessibility, use a **Ghost Border**:
- **Token:** `outline-variant` (#c4c6d0) at **15% opacity**. It should be felt, not seen.

## 5. Components

### Entity Tags (Specialized)
The core of the redaction experience. 
- **Style:** Use `secondary_container` (#d6e0f6) with `on_secondary_container` text. 
- **Shape:** `rounded-sm` (0.125rem) to mimic the look of a highlighter stroke. 
- **Interaction:** On hover, shift to `primary_fixed` to signal the intent to redact.

### Buttons
- **Primary:** Gradient fill (`primary` to `primary_container`), `on_primary` text, `rounded-md`.
- **Secondary:** No fill. `primary` text. Use a `surface-container-high` background on hover.
- **Tertiary (Redact Action):** `tertiary_container` fill. This is your "Redact" button—intentional, high-contrast, and serious.

### Cards & Lists
**Strict Rule:** No dividers (`<hr>`). 
- Separate list items using `spacing-4` (1rem) of vertical white space or by alternating background tones between `surface` and `surface-container-low`.

### Status Indicators
- **Processing:** A subtle pulse effect using `surface-tint` (#455f88) with `0.5` opacity.
- **Complete:** A solid `primary` icon with `label-md` text. Avoid "Success Green" to maintain the professional Navy/Blue aesthetic; trust is built through brand consistency, not traffic light colors.

### Input Fields
- **Style:** "Bottom-line" only or subtle `surface-container-high` fills. 
- **Focus:** Transition the background to `surface-container-lowest` and add a `2px` `primary` underline. No full-box focus rings.

## 6. Do's and Don'ts

### Do:
- **Use Asymmetry:** Align document previews to the left with a wide, right-aligned inspector panel to create an editorial layout.
- **Embrace White Space:** Use `spacing-12` and `spacing-16` to separate major functional groups.
- **Use Tonal Nesting:** Put a `surface-container-highest` element inside a `surface-container` to show deep "drilled-down" data.

### Don't:
- **Don't use 1px Borders:** Never use a solid `#ccc` or `outline` border to wrap a card.
- **Don't use Pure Black:** Use `primary` or `on_surface` (#181c1e) for text to keep the "Navy" brand soul.
- **Don't use Standard Shadows:** Avoid any shadow with more than 10% opacity; it breaks the "Vellum/Glass" aesthetic.
- **Don't use Rounded Corners for Everything:** Use `rounded-none` or `rounded-sm` for the document viewer to maintain a sense of "Official Paper," while using `rounded-xl` for floating action buttons.