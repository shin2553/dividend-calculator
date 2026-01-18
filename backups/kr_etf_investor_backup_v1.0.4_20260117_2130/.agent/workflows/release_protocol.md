---
description: Protocol for releasing a new version
---

# Release Protocol

Follow these steps for every new release:

1.  **Update Documentation**:
    *   Update `ReleaseNotes.md`: Add a new section for the version, date, and detailed changelog.
    *   Update `Manual.md`: Reflect any new features, UI changes, or logic updates in the user manual. Update the version number in the manual.

2.  **Versioning**:
    *   Update `VERSION` variable in `build_exe.py`.
    *   Update version string in `flask_app.py` (if applicable).
    *   The build script will automatically update version strings in `index.html`.

3.  **Build**:
    *   Run `python build_exe.py`.
    *   This script will:
        *   Update HTML version strings.
        *   Clean previous builds.
        *   Run PyInstaller.
        *   Copy `Manual.md` and `ReleaseNotes.md` to `dist/`.

4.  **Verification**:
    *   Check `dist/` folder for the new executable.
    *   Verify `Manual.md` and `ReleaseNotes.md` are present in `dist/`.
