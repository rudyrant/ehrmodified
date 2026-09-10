from pathlib import Path
from urllib.request import urlopen

# Reuse the complete previous patcher, then fix the C# coroutine restriction
# before executing it. The previous patcher contains the STATS + AutoRemake changes.
url = "https://raw.githubusercontent.com/rudyrant/ehrmodified/8ffca4a8c3ca516d69f8d07ce518f82f715da964/apply-rudyrant-ehr.py"
previous = urlopen(url, timeout=30).read().decode("utf-8")

old = '''            catch (Exception e)
            {
                Logger.Error($"Auto-remake attempt {attempt}/3 failed: {e}", "AutoRemakeManager");
                yield return new WaitForSecondsRealtime(5f);
            }
'''
new = '''            catch (Exception e)
            {
                Logger.Error($"Auto-remake attempt {attempt}/3 failed: {e}", "AutoRemakeManager");
            }
            yield return new WaitForSecondsRealtime(5f);
'''

if old not in previous:
    raise SystemExit("Expected AutoRemake catch block not found in previous patcher")

previous = previous.replace(old, new, 1)
exec(compile(previous, "apply-rudyrant-ehr.py", "exec"), {"__name__": "__main__"})
