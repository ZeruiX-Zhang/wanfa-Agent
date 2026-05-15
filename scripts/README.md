# Reality OS Scripts

The scripts in this folder are Phase 2 command wrappers. They do not migrate business code.

## Doctor

```powershell
.\scripts\check-phase2.ps1
```

or:

```powershell
npm run doctor
```

## Print legacy commands

```powershell
.\scripts\start-legacy.ps1 -Target all
```

or:

```powershell
npm run legacy:list
```

## Run one legacy target

The wrapper prints commands by default. Add `-Run` only when you want to execute a single target.

```powershell
.\scripts\start-legacy.ps1 -Target prompt-backend -Run
```

The wrapper refuses `-Target all -Run` to avoid starting multiple servers with conflicting ports.
