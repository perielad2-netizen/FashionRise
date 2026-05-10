using System.IO;
using FashionRise.Core.Navigation;
using FashionRise.Presentation.Sketch;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Pillar A — raster sketch capture; PNG saved for enhancement / design_data. [AI_READY]</summary>
    public sealed class SketchCanvasScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.SketchCanvas;

        UiSketchPad _pad = null!;
        Text _hint = null!;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Sketch canvas", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B",
                "Draw a rough idea below. Undo reverts the last stroke. Continue saves a PNG and opens enhancement.",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);

            var padGo = new GameObject("SketchPad", typeof(RectTransform), typeof(RawImage), typeof(UiSketchPad));
            padGo.transform.SetParent(col, false);
            var padLe = padGo.AddComponent<LayoutElement>();
            padLe.minHeight = 240f;
            padLe.preferredHeight = 400f;
            padLe.flexibleHeight = 1f;
            var padRt = padGo.GetComponent<RectTransform>();
            padRt.sizeDelta = new Vector2(0f, 400f);
            _pad = padGo.GetComponent<UiSketchPad>();
            var rim = padGo.GetComponent<RawImage>();
            rim.raycastTarget = true;
            rim.color = Color.white;

            _hint = FrUiFactory.AddLabel(col, "Hint", " ", t, Mathf.RoundToInt(t.BodySize * 0.9f), FontStyle.Italic,
                TextAnchor.UpperCenter);

            FrUiFactory.AddButton(col, "Undo", t, () =>
            {
                if (!_pad.UndoStroke())
                    _hint.text = "Nothing to undo.";
                else
                    _hint.text = " ";
            });
            FrUiFactory.AddButton(col, "Clear", t, () =>
            {
                _pad.ClearAll();
                _hint.text = " ";
            });
            FrUiFactory.AddButton(col, "Continue to enhancement", t, ContinueToEnhancement);
            FrUiFactory.AddButton(col, "Import sketch", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ImportSketch);
            });
            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload)
        {
            var pending = App.CreateDesign.PendingReferenceImagePath?.Trim();
            if (string.IsNullOrEmpty(pending))
                return;

            App.CreateDesign.PendingReferenceImagePath = "";
            if (!File.Exists(pending))
            {
                _hint.text = "Reference file is missing.";
                return;
            }

            if (_pad.TryLoadUnderlayFromFile(pending, out var err))
                _hint.text = "Reference loaded — draw on top, or Continue to send the composite.";
            else
                _hint.text = string.IsNullOrEmpty(err) ? "Could not load reference." : err;
        }

        void ContinueToEnhancement()
        {
            if (!_pad.HasInk() && !_pad.HasReferenceUnderlay)
            {
                _hint.text = "Draw something, load a reference (Import → Trace), or use Import → Pipeline for a photo only.";
                return;
            }

            var path = _pad.SavePngToPersistentData("canvas");
            App.CreateDesign.SketchReference = "file:" + path.Replace('\\', '/');
            _hint.text = " ";
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement);
        }
    }
}
