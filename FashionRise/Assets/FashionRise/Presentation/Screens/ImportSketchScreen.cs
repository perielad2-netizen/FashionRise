using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using FashionRise.Config;
using FashionRise.Content;
using FashionRise.Core.Navigation;
using FashionRise.Infrastructure.Platform;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Import PNG/JPEG from persistent Sketches + Imports folders. [V3_READY] native OS picker.</summary>
    public sealed class ImportSketchScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.ImportSketch;

        Transform _listHost = null!;
        Text _info = null!;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Import sketch", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B",
                "Images in your Sketches and Imports folders appear below. Pipeline sends the file as-is to enhancement. Trace loads it under your drawing.",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);

            _info = FrUiFactory.AddLabel(col, "Info", " ", t, Mathf.RoundToInt(t.BodySize * 0.92f), FontStyle.Italic,
                TextAnchor.UpperCenter);

            FrUiFactory.AddButton(col, "Refresh list", t, RefreshList);

            if (AndroidGalleryPick.IsSupported)
                FrUiFactory.AddButton(col, "Pick from gallery (Android)", t, () => AndroidGalleryPick.BeginPickToImportsFolder());

            if (PcImportsFolderOpener.IsSupported)
                FrUiFactory.AddButton(col, "Open Imports folder (PC)", t, PcImportsFolderOpener.TryOpenImportsFolder);

            var listGo = new GameObject("FileList", typeof(RectTransform), typeof(VerticalLayoutGroup));
            listGo.transform.SetParent(col, false);
            var listLe = listGo.AddComponent<LayoutElement>();
            listLe.flexibleHeight = 1f;
            listLe.minHeight = 160f;
            _listHost = listGo.transform;
            var v = listGo.GetComponent<VerticalLayoutGroup>();
            v.spacing = 8f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload) => RefreshList();

        void OnEnable()
        {
            if (AndroidGalleryPick.IsSupported)
                FashionRiseAndroidBridge.GalleryPickCompleted += OnAndroidGalleryCompleted;
        }

        void OnDisable()
        {
            FashionRiseAndroidBridge.GalleryPickCompleted -= OnAndroidGalleryCompleted;
        }

        void OnAndroidGalleryCompleted(string? path)
        {
            if (path == null)
            {
                _info.text = "Gallery selection cancelled or failed.";
                return;
            }

            RefreshList();
            _info.text = "Image saved to Imports. Choose Pipeline or Trace.";
        }

        void RefreshList()
        {
            for (var i = _listHost.childCount - 1; i >= 0; i--)
                Destroy(_listHost.GetChild(i).gameObject);

            var imports = Path.Combine(UnityEngine.Application.persistentDataPath, "Imports");
            var sketches = Path.Combine(UnityEngine.Application.persistentDataPath, "Sketches");
            Directory.CreateDirectory(imports);
            Directory.CreateDirectory(sketches);

            var files = EnumerateImportCandidates().ToList();
            if (files.Count == 0)
            {
                _info.text =
                    "No PNG/JPEG yet. Android: use Pick from gallery. PC: Open Imports folder or save from the canvas.\n" +
                    imports;
                return;
            }

            _info.text = $"{files.Count} file(s) found (newest first).";
            var t = ThemeOrDefault;
            foreach (var path in files)
                AddFileRow(path, t);
        }

        static IEnumerable<string> EnumerateImportCandidates()
        {
            var dirs = new[]
            {
                Path.Combine(UnityEngine.Application.persistentDataPath, "Sketches"),
                Path.Combine(UnityEngine.Application.persistentDataPath, "Imports")
            };
            var acc = new List<(string path, long ticks)>();
            foreach (var dir in dirs)
            {
                if (!Directory.Exists(dir))
                    continue;
                foreach (var f in Directory.GetFiles(dir))
                {
                    var ext = Path.GetExtension(f).ToLowerInvariant();
                    if (ext != ".png" && ext != ".jpg" && ext != ".jpeg")
                        continue;
                    try
                    {
                        acc.Add((f, new FileInfo(f).LastWriteTimeUtc.Ticks));
                    }
                    catch
                    {
                        /* ignore */
                    }
                }
            }

            foreach (var p in acc.OrderByDescending(x => x.ticks).Select(x => x.path))
                yield return p;
        }

        void AddFileRow(string path, FashionRiseTheme theme)
        {
            var row = new GameObject(Path.GetFileName(path) + "_row", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            row.transform.SetParent(_listHost, false);
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 8f;
            h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlHeight = true;
            h.childForceExpandHeight = false;
            h.childControlWidth = true;
            h.childForceExpandWidth = true;
            var rowLe = row.AddComponent<LayoutElement>();
            rowLe.minHeight = DeviceLayoutPolicy.IsTabletLike() ? 52f : 46f;

            var shortName = Path.GetFileName(path);
            if (shortName.Length > 22)
                shortName = shortName[..19] + "…";

            var pathCopy = path;
            FrUiFactory.AddButton(row.transform, "Pipeline · " + shortName, theme, () => UseInPipeline(pathCopy));
            FrUiFactory.AddButton(row.transform, "Trace", theme, () => OpenOnCanvas(pathCopy));
        }

        void UseInPipeline(string path)
        {
            App.CreateDesign.SketchReference = "file:" + path.Replace('\\', '/');
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement);
        }

        void OpenOnCanvas(string path)
        {
            App.CreateDesign.PendingReferenceImagePath = path;
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchCanvas);
        }
    }
}
