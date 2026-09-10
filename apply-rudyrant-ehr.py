from pathlib import Path

root = Path("extracted/EndlessHostRoles-main")

lobby = root / "Modules" / "LobbySharingAPI.cs"
text = lobby.read_text(encoding="utf-8-sig")

if "using System.IO;" not in text:
    text = text.replace("using System.Diagnostics.CodeAnalysis;\n", "using System.Diagnostics.CodeAnalysis;\nusing System.IO;\nusing System.Linq;\nusing System.Reflection;\n", 1)

marker = '\n[SuppressMessage("ReSharper", "InconsistentNaming")]\npublic enum LobbyStatus'
manager = '''public static class LobbyStatsManager
{
    private const float UpdateInterval = 3f;
    private const string StatsFileName = "STATS.txt";
    private static Coroutine _coroutine;
    private static bool _running;

    public static string StatsPath => Path.Combine(Main.DataPath, StatsFileName);

    public static void Start()
    {
        if (_running || Main.Instance == null) return;
        _running = true;
        _coroutine = Main.Instance.StartCoroutine(UpdateLoop());
    }

    public static void Stop(bool deleteFile = false)
    {
        _running = false;
        if (_coroutine != null)
        {
            Main.Instance?.StopCoroutine(_coroutine);
            _coroutine = null;
        }
        if (deleteFile)
        {
            try { if (File.Exists(StatsPath)) File.Delete(StatsPath); }
            catch (Exception e) { Logger.Error($"Failed to remove {StatsPath}: {e}", "LobbyStatsManager"); }
        }
    }

    private static System.Collections.IEnumerator UpdateLoop()
    {
        while (_running)
        {
            try
            {
                if (AmongUsClient.Instance && AmongUsClient.Instance.AmHost && GameStates.IsLobby)
                    WriteStats();
                else if (AmongUsClient.Instance && AmongUsClient.Instance.AmHost && GameStates.IsInGame)
                    WriteStats();
            }
            catch (Exception e) { Logger.Error($"STATS.txt update failed: {e}", "LobbyStatsManager"); }
            yield return new WaitForSecondsRealtime(UpdateInterval);
        }
    }

    private static void WriteStats()
    {
        string roomCode = string.Empty;
        try { roomCode = GameCode.IntToGameName(AmongUsClient.Instance.GameId); } catch { }
        string region = "Unknown";
        try { region = Utils.GetRegionName(); } catch { }
        string map = "Unknown";
        try { map = Options.RandomMapsMode.GetBool() ? "Random" : Main.CurrentMap.ToString(); } catch { }
        string gameMode = "Unknown";
        try { gameMode = Options.EnableAutoGMRotation.GetBool() ? "Rotating" : Options.CurrentGameMode.ToString(); } catch { }
        string state = GameStates.IsInGame || AmongUsClient.Instance.IsGameStarted ? "INGAME" : "OPEN";
        int playerCount = 0;
        try { playerCount = PlayerControl.AllPlayerControls.Count; } catch { }
        int maxPlayers = 0;
        try { maxPlayers = Main.NormalOptions?.MaxPlayers ?? 0; } catch { }
        string hostName = "Unknown";
        byte hostId = byte.MaxValue;
        try
        {
            if (PlayerControl.LocalPlayer)
            {
                hostName = PlayerControl.LocalPlayer.GetRealName().RemoveHtmlTags();
                hostId = PlayerControl.LocalPlayer.PlayerId;
            }
        }
        catch { }
        string serverType = "Unknown";
        try { serverType = GameStates.CurrentServerType.ToString(); } catch { }
        string preset = "Unknown";
        try { preset = OptionItem.CurrentPreset.ToString(); } catch { }
        string networkMode = "Unknown";
        try { networkMode = AmongUsClient.Instance.NetworkMode.ToString(); } catch { }
        string gameId = "Unknown";
        try { gameId = AmongUsClient.Instance.GameId.ToString(); } catch { }
        string output =
            $"Code: {roomCode}\\n" +
            $"Region: {region}\\n" +
            $"Map: {map}\\n" +
            $"Game Mode: {gameMode}\\n" +
            $"Preset: {preset}\\n" +
            $"Players: {playerCount}/{maxPlayers}\\n" +
            $"Lobby State: {state}\\n" +
            $"Host: {hostName}\\n" +
            $"Host Player ID: {hostId}\\n" +
            $"Server Type: {serverType}\\n" +
            $"Network Mode: {networkMode}\\n" +
            $"Game ID: {gameId}\\n" +
            $"EHR Version: {Main.PluginVersion}\\n" +
            $"Game Version: {Main.SupportedAUVersion}\\n" +
            $"Updated: {DateTime.Now:yyyy-MM-dd HH:mm:ss}\\n";
        string tempPath = StatsPath + ".tmp";
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(StatsPath)!);
            File.WriteAllText(tempPath, output, new UTF8Encoding(false));
            File.Move(tempPath, StatsPath, true);
        }
        catch
        {
            try { if (File.Exists(tempPath)) File.Delete(tempPath); } catch { }
            throw;
        }
    }
}

public static class AutoRemakeManager
{
    private const string ConfigFileName = "EHR_DATA/AutoRemake.txt";
    private static readonly HashSet<DisconnectReasons> UnexpectedReasons =
    [
        DisconnectReasons.ClientTimeout,
        DisconnectReasons.ConnectionLimit,
        DisconnectReasons.Error,
        DisconnectReasons.GameNotFound,
        DisconnectReasons.IncorrectVersion,
        DisconnectReasons.Kicked,
        DisconnectReasons.ServerError,
        DisconnectReasons.ServerNotFound,
        DisconnectReasons.ServerRequest,
        DisconnectReasons.Unknown
    ];
    private static string SavedRegionName = string.Empty;
    private static bool WasHost;
    private static bool WasOnline;
    public static string ConfigPath => Path.Combine(Main.DataPath, ConfigFileName);
    public static bool Enabled
    {
        get
        {
            try { return File.Exists(ConfigPath) && File.ReadAllText(ConfigPath).Trim().Equals("ON", StringComparison.OrdinalIgnoreCase); }
            catch { return false; }
        }
    }
    public static void CaptureLobbyState()
    {
        if (!AmongUsClient.Instance || !AmongUsClient.Instance.AmHost) return;
        WasHost = true;
        WasOnline = GameStates.IsOnlineGame;
        try { SavedRegionName = ServerManager.Instance.CurrentRegion?.Name ?? string.Empty; }
        catch { SavedRegionName = string.Empty; }
    }
    public static void HandleDisconnect(DisconnectReasons reason)
    {
        if (!WasHost || !WasOnline || !Enabled || !UnexpectedReasons.Contains(reason))
        {
            WasHost = false; WasOnline = false; return;
        }
        string region = SavedRegionName;
        WasHost = false; WasOnline = false;
        Logger.Msg($"Unexpected host disconnect ({reason}). Auto-remake is enabled; recreating lobby in region '{region}'.", "AutoRemakeManager");
        Main.Instance.StartCoroutine(RemakeAfterDisconnect(region));
    }
    private static System.Collections.IEnumerator RemakeAfterDisconnect(string regionName)
    {
        float timeout = 20f;
        while (timeout > 0f)
        {
            if (AmongUsClient.Instance && AmongUsClient.Instance.GameState == InnerNetClient.GameStates.NotJoined) break;
            timeout -= Time.unscaledDeltaTime;
            yield return null;
        }
        yield return new WaitForSecondsRealtime(2f);
        for (int attempt = 1; attempt <= 3; attempt++)
        {
            try
            {
                RestoreRegion(regionName);
                if (!TryCreateGame()) throw new InvalidOperationException("PSManager.CreateGame could not be invoked.");
                Logger.Msg($"Auto-remake lobby creation requested (attempt {attempt}).", "AutoRemakeManager");
                yield break;
            }
            catch (Exception e)
            {
                Logger.Error($"Auto-remake attempt {attempt}/3 failed: {e}", "AutoRemakeManager");
                yield return new WaitForSecondsRealtime(5f);
            }
        }
    }
    private static void RestoreRegion(string regionName)
    {
        if (string.IsNullOrWhiteSpace(regionName) || ServerManager.Instance == null) return;
        try
        {
            IRegionInfo region = ServerManager.Instance.AvailableRegions.FirstOrDefault(x => string.Equals(x.Name, regionName, StringComparison.OrdinalIgnoreCase));
            if (region == null) return;
            PropertyInfo currentRegion = ServerManager.Instance.GetType().GetProperty("CurrentRegion", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (currentRegion?.CanWrite == true) { currentRegion.SetValue(ServerManager.Instance, region); return; }
            MethodInfo setter = ServerManager.Instance.GetType().GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                .FirstOrDefault(m => (m.Name.Contains("SetRegion", StringComparison.OrdinalIgnoreCase) || m.Name.Contains("SelectRegion", StringComparison.OrdinalIgnoreCase)) && m.GetParameters().Length == 1 && m.GetParameters()[0].ParameterType.IsAssignableFrom(region.GetType()));
            setter?.Invoke(ServerManager.Instance, [region]);
        }
        catch (Exception e) { Logger.Error($"Failed to restore region '{regionName}': {e}", "AutoRemakeManager"); }
    }
    private static bool TryCreateGame()
    {
        Type psManagerType = typeof(PSManager);
        MethodInfo createGame = psManagerType.GetMethods(BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .FirstOrDefault(m => m.Name == "CreateGame" && m.GetParameters().Length == 0);
        if (createGame == null) return false;
        object target = null;
        if (!createGame.IsStatic)
        {
            PropertyInfo instanceProperty = psManagerType.GetProperty("Instance", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
            target = instanceProperty?.GetValue(null);
            if (target == null) return false;
        }
        createGame.Invoke(target, null);
        return true;
    }
}
'''
if "public static class LobbyStatsManager" not in text:
    if marker not in text: raise SystemExit("LobbyStatus anchor not found")
    text = text.replace(marker, "\n" + manager + marker, 1)
old = """    public static void Prefix(InnerNetClient __instance, DisconnectReasons reason)\n    {\n        if (__instance is not AmongUsClient) return;\n\n        Logger.Msg($\"Exiting game - reason: {reason}\", \"ExitGamePatch.Prefix\");"""
new = """    public static void Prefix(InnerNetClient __instance, DisconnectReasons reason)\n    {\n        if (__instance is not AmongUsClient) return;\n\n        AutoRemakeManager.CaptureLobbyState();\n        Logger.Msg($\"Exiting game - reason: {reason}\", \"ExitGamePatch.Prefix\");"""
if "AutoRemakeManager.CaptureLobbyState();" not in text:
    if old not in text: raise SystemExit("ExitGame Prefix anchor not found")
    text = text.replace(old, new, 1)
old = """    public static void Postfix(InnerNetClient __instance)\n    {\n        if (__instance is not AmongUsClient) return;\n\n        LobbySharingAPI.NotifyLobbyStatusChanged(LobbyStatus.Closed);"""
new = """    public static void Postfix(InnerNetClient __instance, DisconnectReasons reason)\n    {\n        if (__instance is not AmongUsClient) return;\n\n        LobbyStatsManager.Stop();\n        AutoRemakeManager.HandleDisconnect(reason);\n        LobbySharingAPI.NotifyLobbyStatusChanged(LobbyStatus.Closed);"""
if "AutoRemakeManager.HandleDisconnect(reason);" not in text:
    if old not in text: raise SystemExit("ExitGame Postfix anchor not found")
    text = text.replace(old, new, 1)
lobby.write_text(text, encoding="utf-8")

join = root / "Patches" / "PlayerJoinAndLeftPatch.cs"
text = join.read_text(encoding="utf-8-sig")
old = """        if (AmongUsClient.Instance.AmHost)\n        {\n            GameStartManagerPatch.GameStartManagerUpdatePatch.ExitTimer = -1;"""
new = """        if (AmongUsClient.Instance.AmHost)\n        {\n            LobbyStatsManager.Start();\n            AutoRemakeManager.CaptureLobbyState();\n\n            GameStartManagerPatch.GameStartManagerUpdatePatch.ExitTimer = -1;"""
if "LobbyStatsManager.Start();" not in text:
    if old not in text: raise SystemExit("OnGameJoined host anchor not found")
    text = text.replace(old, new, 1)
join.write_text(text, encoding="utf-8")
print("RudyRant EHR modifications applied.")
