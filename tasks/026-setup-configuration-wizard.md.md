# Task 026 — Setup & Configuration Wizard

## Objective

Provide a guided Web UI setup experience that allows a normal user to configure the Legal Platform after installation without manually editing source code or configuration files.

The wizard must configure the AI/runtime capabilities provided by Task 025 and the existing application infrastructure.

The Web UI is the primary setup interface.

A normal user should be able to go from a fresh installation to a usable application by following the wizard.

---

## Scope

### 1. First-run detection

Detect whether the application has completed initial configuration.

On first launch, show the Setup Wizard instead of assuming that the user already understands the application's configuration.

After successful setup, the normal application UI should be shown.

The wizard must be repeatable from Settings when appropriate.

---

## 2. Setup strategy

The first decision should be:

```text
How would you like to run AI services?

○ Local
  Run supported AI components on this computer.

○ Cloud
  Use remote AI services.

○ Hybrid
  Choose local or cloud independently for each AI component.
