# Docker Layer Cache Verification Report

## Dockerfile Layer Ordering Analysis

### ✅ **VERDICT: Dockerfile Structure is CORRECT**

The Dockerfile follows optimal layer ordering:

#### Builder Stage (Lines 4-18)
```
FROM python:3.13-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y ...  # System deps
COPY requirements.txt ./                      # ✅ Dependencies FIRST
COPY api/requirements.txt ./api/              # ✅ Dependencies FIRST
RUN pip install ...                           # ✅ Install AFTER copying deps
```

#### Production Stage (Lines 21-82)
```
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ...  # System deps (stable)
RUN wget ... dotnet-install.sh ...            # .NET SDK (stable)
RUN dotnet tool install --global dafny        # Dafny (stable)
RUN curl ... z3 ...                           # Z3 solver (stable)
COPY --from=builder /root/.local /root/.local # Python packages (stable)
COPY . .                                      # ✅ Application code LAST
```

**Key Finding:** `COPY . .` is at line 66, **after** all dependency installation. This is correct!

### Expected Cache Behavior

With correct layer ordering, these layers should be **CACHED** on subsequent builds:
- ✅ Base Python image
- ✅ System dependencies (apt-get)
- ✅ .NET SDK installation
- ✅ Dafny installation  
- ✅ Z3 solver installation
- ✅ Python packages (from builder stage)
- ⚠️ Application code layer (`COPY . .`) - invalidates on code changes (expected)

## Cache Configuration

Current workflow uses multi-scope cache strategy:
```yaml
cache-from: |
  type=gha,scope=global
  type=gha,scope=refs/heads/main
  type=gha,scope=${{ github.ref }}
cache-to: type=gha,mode=max,scope=global
```

## How to Verify Cache Hits

### Step 1: Check GitHub Actions Logs

Navigate to: `Actions` → Select workflow run → `Build and Cache API Image` step

### Step 2: Look for "CACHED" Indicators

**✅ Success Pattern (Cache Working):**
```
[+] Building 1.2s (12/12) FINISHED
 => [internal] load build definition from Dockerfile  0.0s
 => [internal] load metadata for docker.io/library/python:3.13-slim  0.4s
 => [1/6] FROM docker.io/library/python:3.13-slim  0.0s
 => CACHED [2/6] RUN apt-get update && apt-get install -y ...  0.0s  ← CACHED
 => CACHED [3/6] RUN wget https://dot.net/v1/dotnet-install.sh ...  0.0s  ← CACHED
 => CACHED [4/6] RUN dotnet tool install --global dafny  0.0s  ← CACHED
 => CACHED [5/6] RUN curl -L https://github.com/Z3Prover/z3/...  0.0s  ← CACHED
 => CACHED [6/6] COPY --from=builder /root/.local /root/.local  0.0s  ← CACHED
 => [7/7] COPY . .  2.1s  ← Only this should rebuild on code changes
```

**❌ Failure Pattern (Cache Miss):**
```
[+] Building 45.3s (12/12) FINISHED
 => [2/6] RUN apt-get update && apt-get install -y ...  8.2s  ← NO "CACHED" tag
 => [3/6] RUN wget https://dot.net/v1/dotnet-install.sh ...  12.5s  ← NO "CACHED" tag
 => [4/6] RUN dotnet tool install --global dafny  15.3s  ← NO "CACHED" tag
```

### Step 3: Verify Cache Backend Messages

Look for cache-related messages in the build output:
- `#1 [internal] load cache manifest`
- `#2 importing cache manifest from gha`
- `Cache saved with ID: ...`

## Potential Issues

### Issue 1: Context Changes Invalidating Cache
If ANY file in the build context changes, Docker recalculates checksums. However, with correct layer ordering, only the final `COPY . .` layer should rebuild.

### Issue 2: Cache Scope Not Working
If cache scope configuration is incorrect, cache might not be shared across branches. Current configuration uses:
- Global scope (shared)
- Main branch scope (explicit fallback)
- Current branch scope (local fallback)

### Issue 3: First Build Has No Cache
The first build after merging will always be a full build. Subsequent builds should use cache.

## Recommendations

1. **Monitor Build Times:**
   - First build: ~5-10 minutes (full build)
   - Cached build: ~30-60 seconds (only code layer rebuilds)

2. **Verify Cache Persistence:**
   - Run workflow twice on the same branch
   - Second run should show "CACHED" for dependency layers

3. **Check Cache Size:**
   - GitHub Actions cache limit: 10GB per repository
   - Monitor cache usage in repository settings

## Next Steps

1. ✅ Dockerfile structure verified - **CORRECT**
2. ⏳ Check GitHub Actions logs for "CACHED" indicators
3. ⏳ Verify build times match expected patterns
4. ⏳ Confirm cache is being written and read correctly

## Action Items

- [ ] Review latest workflow run logs
- [ ] Confirm "CACHED" tags appear for dependency layers
- [ ] Measure build time improvement
- [ ] Report findings back
