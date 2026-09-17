using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace FashionRise.Core
{
    /// <summary>
    /// Flight recorder. Breadcrumbs and every error/exception are appended to
    /// <c>&lt;persistentDataPath&gt;/fashionrise-diag.log</c> and flushed immediately, so a hard
    /// editor/player crash still leaves the last step behind. Also catches the two exception
    /// classes Unity swallows: unobserved <see cref="Task"/> faults and unhandled domain errors.
    /// </summary>
    public static class FrDiag
    {
        const long MaxBytes = 512 * 1024;

        static readonly object Gate = new();
        static string _path = "";
        static bool _installed;
        static bool _writing;

        public static string LogPath => _path;

        /// <summary>Call once from the main thread as early as possible.</summary>
        public static void Install()
        {
            if (_installed)
                return;
            _installed = true;

            try
            {
                var dir = UnityEngine.Application.persistentDataPath;
                _path = Path.Combine(dir, "fashionrise-diag.log");
                Directory.CreateDirectory(dir);
                if (File.Exists(_path) && new FileInfo(_path).Length > MaxBytes)
                    File.Delete(_path);
            }
            catch
            {
                _path = "";
            }

            UnityEngine.Application.logMessageReceivedThreaded += OnUnityLog;
            AppDomain.CurrentDomain.UnhandledException += (_, e) =>
                Write("FATAL", "AppDomain unhandled: " + e.ExceptionObject);
            TaskScheduler.UnobservedTaskException += (_, e) =>
            {
                e.SetObserved();
                Write("TASK", "Unobserved task exception: " + e.Exception);
                Debug.LogWarning("FashionRise unobserved task exception: " + e.Exception.Message);
            };

            Write("BOOT",
                $"FashionRise {UnityEngine.Application.version} on {UnityEngine.Application.platform} " +
                $"unity={UnityEngine.Application.unityVersion}");
            Debug.Log($"FashionRise diagnostics → {_path}");
        }

        /// <summary>Breadcrumb: one short line for a step we want to see in a post-crash log.</summary>
        public static void Step(string message)
        {
            Write("STEP", message);
            Debug.Log("FashionRise " + message);
        }

        /// <summary>Breadcrumb without console noise (per-frame / high volume steps).</summary>
        public static void Trace(string message) => Write("TRACE", message);

        public static void Fail(string context, Exception? ex)
        {
            Write("FAIL", context + " :: " + ex);
            Debug.LogWarning($"FashionRise {context}: {ex?.Message}");
        }

        /// <summary>
        /// Fire-and-forget with a safety net. Unity never surfaces faults from discarded tasks,
        /// which is how a broken screen turns into "the app just died with no log".
        /// </summary>
        public static void Fire(Task? task, string context)
        {
            if (task == null)
                return;
            task.ContinueWith(t => Fail(context, t.Exception?.GetBaseException()),
                CancellationToken.None, TaskContinuationOptions.OnlyOnFaulted,
                TaskScheduler.Default);
        }

        static void OnUnityLog(string condition, string stackTrace, LogType type)
        {
            if (type is LogType.Log or LogType.Warning)
                return;
            Write(type.ToString().ToUpperInvariant(),
                condition + (string.IsNullOrEmpty(stackTrace) ? "" : "\n" + stackTrace.TrimEnd()));
        }

        static void Write(string kind, string message)
        {
            if (string.IsNullOrEmpty(_path))
                return;
            lock (Gate)
            {
                if (_writing)
                    return; // a failing write must not re-enter through the Unity log hook
                _writing = true;
                try
                {
                    var line = new StringBuilder()
                        .Append(DateTime.Now.ToString("HH:mm:ss.fff"))
                        .Append(" | ")
                        .Append(kind)
                        .Append(" | ")
                        .Append(message)
                        .Append('\n')
                        .ToString();
                    File.AppendAllText(_path, line, Encoding.UTF8);
                }
                catch
                {
                    _path = "";
                }
                finally
                {
                    _writing = false;
                }
            }
        }
    }
}
