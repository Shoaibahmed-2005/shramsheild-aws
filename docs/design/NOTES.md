# ShramShield — Frontend Design Notes

## 1. Primary Instruction: Understand the Project Before Designing

**The project specification takes priority over every design reference image.**

Before implementing the frontend, carefully read:

- `AGENTS.md` at the repository root.
- Sections 0 and 3 of `docs/BUILD_PLAN.md`.
- The P3.1 task card in section 4 of `docs/BUILD_PLAN.md`.
- The relevant fixture files and data contracts referenced by the task.

Understand the complete problem statement, the purpose of ShramShield, its required functionality, the four dashboard routes, the data structures, the risk classifications, and the accessibility requirements.

The reference images are provided ONLY to communicate the preferred visual style. They are not templates that must be reproduced exactly.

**Do not blindly copy the sections, cards, charts, navigation layouts, labels, information, or features shown in the reference images.**

Instead:
- Determine what information and components are actually required by the project specification.
- Display only the information necessary to fulfil the requirements of each page.
- Organise that information into the cleanest and most understandable interface.
- Adapt the visual style to ShramShield's heat-safety use case.
- Exclude unrelated features, decorative sections, and unnecessary components just because they appear in a reference image.
- Do not invent additional functionality beyond the task requirements.
- If something is not defined by the project contract, do not silently invent it.

The goal is to create a purpose-built interface for ShramShield, not a recreation of another application's design.

## 2. Design Direction

Create a clean, modern, professional dashboard inspired by the uploaded mobile calorie-counter reference.

The reference is appealing because it uses a simple layout, generous spacing, rounded cards, subtle shadows, pastel colours, clear typography, and well-organised information.

Use these visual principles while adapting the actual layout to the requirements of a heat-safety operations dashboard.

The overall interface should feel:
- Minimal and professional.
- Friendly without looking childish.
- Information-rich without feeling crowded.
- Consistent across all four pages.
- Suitable for a serious cybersecurity, environmental safety, or engineering project demonstration.

## 3. Colour Palette

Use a restrained pastel palette for the general interface.

- **Background:** Warm off-white or very light blue-grey.
- **Cards:** White or very subtle pastel surfaces.
- **Primary accent:** Muted sky blue.
- **Secondary accents:** Pastel mint green, soft yellow, peach, and lavender.
- **Text:** Dark navy or charcoal for strong readability.
- **Borders and dividers:** Thin, light grey.
- **Shadows:** Soft and subtle, never excessive.

Keep the colours consistent across the application. Avoid loud backgrounds, excessive gradients, unnecessary decorative colour blocks, and strong shadows on every element.

### Heat-risk colour exception

The exact risk-level colours and text contrast specified in `docs/BUILD_PLAN.md` must be preserved.

Use the values defined in the project contract for GREEN, YELLOW, ORANGE, RED, STOP, and UNKNOWN. These colours take priority over the general pastel palette because users must distinguish heat-risk levels correctly.

Do not change a risk colour simply to make the interface match a reference image.

## 4. Layout and Components

Follow the general visual principles of the reference images, not their exact arrangement.

- Use clean cards with consistent spacing and rounded corners.
- Group related information together logically.
- Maintain generous whitespace.
- Align headings, descriptions, metrics, and labels consistently.
- Use a clear typography hierarchy.
- Prefer simple navigation and intuitive page structures.
- Make important safety information immediately noticeable.
- Avoid overcrowding the dashboard with unnecessary statistics or repeated information.
- Ensure that every component has a clear purpose.

Use simple, consistent line icons where they help users understand the interface. Maintain the same icon style throughout the application.

Do not add sections simply because there is space available on the screen.

## 5. No Emojis, Faces, or Human Illustrations

**Do not use emojis anywhere in the application.**

Do not include:
- Human faces or profile photographs.
- Portraits or avatar images.
- Illustrations of standing workers or other people.
- Cartoon characters.
- Decorative photographs unrelated to the project's functionality.

Use professional line icons, charts, clear labels, and data visualisations instead.

Weather, location, safety, temperature, clock, calendar, chart, shield, notification, and acknowledgement icons are appropriate where needed.

Keep the design focused on the information and functionality of the product.

## 6. Required ShramShield Pages

Follow the four routes specified in the build plan. Do not add unrelated pages or change the project's routing contract.

### Sites Dashboard — `#/`

Display the four configured demo sites: Chennai, Delhi, Kolkata, and Hyderabad.

Use site cards containing the information required by the Site object, with relevant workload, working-hour, language, and status information where appropriate.

Provide a clear action to view each site's plan.

Use the actual fixture or API data. Do not invent readings or site statuses.

### Site Plan — `#/site/{site_id}`

This page should provide a clear hourly heat-safety plan for the selected site.

Include the required:
- Site details and work profile.
- Twenty-four-hour heat strip.
- Risk-level legend and readable labels.
- Selectable hourly cells.
- Selected-hour weather metrics and WBGT.
- Recommended work/rest duration.
- Explanation of the classification.
- Daily risk windows.
- English/Hindi message switch.
- Required project disclaimer.

Present the information in a clear hierarchy. Do not reproduce unrelated weather-app features, maps, sunrise cards, or other components unless explicitly required by the project specification.

### Backtest — `#/backtest`

Present the historical comparison for April to June 2024 using the actual backtest data.

Include the required summary, temperature-threshold comparison, site-level results, example hour, and limitations.

Use simple charts and tables where they improve understanding. Never invent historical statistics, percentages, or chart values.

### Method — `#/method`

Explain what WBGT is, the specified risk levels, screening limits, data sources, calculation methodology, and limitations.

Keep the explanation readable and organised. Prioritise scientific accuracy and honest communication over decoration.

## 7. Data Accuracy and Project Integrity

The project specification and shared data contract are the source of truth.

- Use fixture data during mock development.
- Use the real API responses when live mode is enabled.
- Keep fixture data clearly identified with the required demo-data badge.
- Never display fixture data as if it were live.
- Never invent weather values, WBGT readings, risk levels, thresholds, historical statistics, notification outcomes, or timestamps.
- Do not modify the project's data structures, route names, or required disclaimer to accommodate the design.
- If data is unavailable, display the appropriate UNKNOWN, loading, empty, or error state according to the contract.
- Do not silently fall back to fixture data when the live API fails.

Design references determine the appearance of the application. The build plan, task card, fixtures, and contract determine its content and behaviour.

## 8. Accessibility and Responsiveness

- Use readable font sizes and sufficient text contrast.
- Support keyboard navigation across all controls.
- Provide visible focus indicators and meaningful accessible labels.
- Never communicate a heat-risk level using colour alone.
- Use semantic HTML and accessible buttons.
- Ensure the hourly heat strip works using a keyboard.
- Keep layouts usable at 360px, 768px, and 1280px widths.
- Support text zoom up to 200% without horizontal overflow.
- Include appropriate loading, error, and empty states.

## 9. Implementation Constraints

Follow the dependencies and technical constraints stated in the P3.1 task card.

Use React, Vite, and JavaScript as specified. Do not introduce additional UI libraries, chart libraries, CSS frameworks, icon packs, or routing libraries that are not permitted by the task.

Keep reusable UI logic organised and testable. Use CSS and the approved dependencies to achieve the intended visual quality.

## 10. Final Design Goal

Create a professional, clean, pastel-themed ShramShield interface that is visually inspired by the supplied references while being purpose-built for the actual heat-safety problem.

The finished dashboard must:
- Display the information genuinely required by the specification.
- Avoid copying unrelated reference-image content.
- Remain simple, readable, and visually consistent.
- Preserve all project data and classification rules.
- Work correctly with fixtures and, in later stages, the live API.
- Be accessible, responsive, and suitable for a professional hackathon demonstration.

**Priority order: Project requirements first, data correctness second, usability and accessibility third, visual polish fourth.**

The reference images inspire the design; they do not define the product.
