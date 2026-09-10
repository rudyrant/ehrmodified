from pathlib import Path

root = Path("extracted/EndlessHostRoles-main")

lobby = root / "Modules" / "LobbySharingAPI.cs"
text = lobby.read_text(encoding="utf-8-sig")

if "using System.Collections.Generic;" not in text:
    text = text.replace("using System.Diagnostics.CodeAnalysis;\n", "using System.Diagnostics.CodeAnalysis;\nusing System.Collections.Generic;\nusing System.IO;\nusing System.Linq;\nusing System.Reflection;\n", 1)

# Fix the C# restriction that yield cannot appear inside a catch block.
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
if old in text:
    text = text.replace(old, new, 1)

lobby.write_text(text, encoding="utf-8")
print("RudyRant EHR modifications applied.")
