using System.IO;
using FashionRise.Application;
using FashionRise.Content;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Presentation.Sketch;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Pillar A — dual-layer sketch: croquis/photo underlay + pro ink tools.</summary>
    public sealed class SketchCanvasScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.SketchCanvas;

        UiSketchPad _pad = null!;
        Text _hint = null!;
        Button _eraseBtn = null!;
        Button _dimRefBtn = null!;
        bool _refDimmed;
        FashionRiseTheme _theme = null!;
        bool _padBootstrapped;

        void Awake()
        {
            var t = ThemeOrDefault;
            _theme = t;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Sketch canvas", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B",
                "Reference below (croquis or your photo). Draw on the layer above — colors, brush size, eraser. Continue saves the combined PNG.",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter, useSecondaryTextColor: true);

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

            AddFigureRow(col, t);
            AddToolRow(col, t);

            FrUiFactory.AddButton(col, "Undo", t, () =>
            {
                if (!_pad.UndoStroke())
                    _hint.text = "Nothing to undo.";
                else
                    _hint.text = " ";
            });
            FrUiFactory.AddButton(col, "Clear drawing", t, () =>
            {
                _pad.ClearAll();
                _hint.text = "Drawing cleared; reference unchanged.";
            });
            FrUiFactory.AddButton(col, "Continue to enhancement", t, ContinueToEnhancement, FrButtonEmphasis.Primary);
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

        void AddFigureRow(Transform col, FashionRiseTheme t)
        {
            var row = NewToolbarRow(col);
            AddTightButton(row, "Female", t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Female;
                _pad.ApplyDefaultFigure(SketchFigureTemplate.Female);
                _hint.text = "Female model — draw on top.";
            });
            AddTightButton(row, "Male", t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Male;
                _pad.ApplyDefaultFigure(SketchFigureTemplate.Male);
                _hint.text = "Male model — draw on top.";
            });
            AddTightButton(row, "Custom…", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ImportSketch);
            });
            AddTightButton(row, "Blank paper", t, () =>
            {
                _pad.ClearReferenceToBlank();
                _hint.text = "White reference — draw freely.";
            });
            _dimRefBtn = AddTightButton(row, "Dim ref", t, ToggleReferenceDim);
        }

        void AddToolRow(Transform col, FashionRiseTheme t)
        {
            var row = NewToolbarRow(col);
            AddTightButton(row, "Thin", t, () => SetRadius(2));
            AddTightButton(row, "Med", t, () => SetRadius(5));
            AddTightButton(row, "Thick", t, () => SetRadius(10));
            AddTightButton(row, "Bold", t, () => SetRadius(18));
            AddTightButton(row, "Black", t, () => SetInk(new Color(0.11f, 0.09f, 0.08f), false));
            AddTightButton(row, "Blue", t, () => SetInk(new Color(0.14f, 0.22f, 0.52f), false));
            AddTightButton(row, "Red", t, () => SetInk(new Color(0.62f, 0.12f, 0.18f), false));
            AddTightButton(row, "Grey", t, () => SetInk(new Color(0.42f, 0.40f, 0.38f), false));
            AddTightButton(row, "Draw", t, () => SetInk(_pad.BrushColor, false));
            _eraseBtn = AddTightButton(row, "Erase", t, () => SetInk(default, true));
        }

        static Transform NewToolbarRow(Transform col)
        {
            var go = new GameObject("ToolbarRow", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            go.transform.SetParent(col, false);
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = 50f;
            le.preferredHeight = 50f;
            le.flexibleWidth = 1f;
            var h = go.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 6f;
            h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlHeight = true;
            h.childForceExpandHeight = false;
            h.childControlWidth = true;
            h.childForceExpandWidth = false;
            h.padding = new RectOffset(0, 0, 0, 0);
            return go.transform;
        }

        Button AddTightButton(Transform row, string label, FashionRiseTheme t, UnityAction onClick)
        {
            var b = FrUiFactory.AddButton(row, label, t, onClick);
            var le = b.GetComponent<LayoutElement>();
            le.flexibleWidth = 0f;
            le.minWidth = 72f;
            le.preferredWidth = 0f;
            return b;
        }

        void SetRadius(int r)
        {
            _pad.SetBrushRadius(r);
            _pad.EraserActive = false;
            RefreshEraseButtonStyle();
            _hint.text = $"Brush size {r}px.";
        }

        void SetInk(Color c, bool eraser)
        {
            if (!eraser)
                _pad.SetBrushColor(c);
            _pad.EraserActive = eraser;
            RefreshEraseButtonStyle();
            _hint.text = eraser ? "Eraser — remove ink only." : "Brush.";
        }

        void RefreshEraseButtonStyle()
        {
            var img = _eraseBtn != null ? _eraseBtn.GetComponent<Image>() : null;
            if (img == null)
                return;
            img.color = _pad.EraserActive ? new Color(0.95f, 0.82f, 0.78f, 1f) : _theme.ButtonFace;
        }

        void ToggleReferenceDim()
        {
            _refDimmed = !_refDimmed;
            _pad.ReferenceStrength = _refDimmed ? 0.4f : 1f;
            _pad.RefreshComposite();
            var txt = _dimRefBtn.GetComponentInChildren<Text>();
            if (txt != null)
                txt.text = _refDimmed ? "Bright ref" : "Dim ref";
            _hint.text = _refDimmed ? "Reference dimmed for easier tracing." : "Reference at full strength.";
        }

        void BootstrapPadReference()
        {
            if (App == null)
                return;

            var pending = App.CreateDesign.PendingReferenceImagePath?.Trim();
            if (!string.IsNullOrEmpty(pending) && File.Exists(pending))
            {
                App.CreateDesign.PendingReferenceImagePath = "";
                if (_pad.TryLoadUnderlayFromFile(pending, out var err))
                    _hint.text = "Custom reference loaded — draw on top.";
                else
                {
                    _hint.text = string.IsNullOrEmpty(err) ? "Could not load reference; using default model." : err;
                    _pad.ApplyDefaultFigure(SketchFigurePreferences.DefaultTemplate);
                }
            }
            else
            {
                _pad.ApplyDefaultFigure(SketchFigurePreferences.DefaultTemplate);
                _hint.text = "Default model — switch Male/Female, Dim ref, or Custom photo.";
            }

            RefreshEraseButtonStyle();
        }

        protected override void OnShown(object? payload)
        {
            if (App == null)
                return;

            if (!_padBootstrapped)
            {
                _padBootstrapped = true;
                BootstrapPadReference();
                return;
            }

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
                _hint.text = "Reference loaded — draw on top.";
            else
                _hint.text = string.IsNullOrEmpty(err) ? "Could not load reference." : err;
        }

        void ContinueToEnhancement()
        {
            if (!_pad.HasInk())
            {
                _hint.text = "Draw on the canvas first (ink on croquis, photo, or blank paper).";
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
