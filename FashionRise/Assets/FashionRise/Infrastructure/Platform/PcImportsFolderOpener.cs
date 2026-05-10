using System;
using System.Diagnostics;
using System.IO;
using UnityEngine;

namespace FashionRise.Infrastructure.Platform
{
    /// <summary>Open the app's Imports directory in the OS file manager (desktop / editor).</summary>
    public static class PcImportsFolderOpener
    {
        public static bool IsSupported =>
            UnityEngine.Application.platform is RuntimePlatform.WindowsPlayer
                or RuntimePlatform.WindowsEditor
                or RuntimePlatform.OSXPlayer
                or RuntimePlatform.OSXEditor
                or RuntimePlatform.LinuxPlayer
                or RuntimePlatform.LinuxEditor;

        public static void TryOpenImportsFolder()
        {
            var imports = Path.Combine(UnityEngine.Application.persistentDataPath, "Imports");
            Directory.CreateDirectory(imports);
            var full = Path.GetFullPath(imports);

            try
            {
#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
                Process.Start(new ProcessStartInfo
                {
                    FileName = "explorer.exe",
                    Arguments = full.Replace('/', '\\'),
                    UseShellExecute = true
                });
#elif UNITY_EDITOR_OSX || UNITY_STANDALONE_OSX
                Process.Start("open", full);
#elif UNITY_EDITOR_LINUX || UNITY_STANDALONE_LINUX
                Process.Start("xdg-open", full);
#else
                UnityEngine.Application.OpenURL("file://" + full.Replace("\\", "/"));
#endif
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogWarning($"Could not open Imports folder: {ex.Message}\n{full}");
            }
        }
    }
}
