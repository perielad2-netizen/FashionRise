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
            root.GetComponent<Image>().color = Color.white;
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Your sketch", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B",
                "Draw clothes on the model. When you are happy, tap Magic!",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter, useSecondaryTextColor: true);

            // Flexible host fills leftover space; pad fits inside at pad texture aspect (no stretch on tablet).
            var hostGo = new GameObject("SketchPadHost", typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            hostGo.transform.SetParent(col, false);
            var hostImg = hostGo.GetComponent<Image>();
            hostImg.color = Color.white;
            hostImg.raycastTarget = false;
            var hostLe = hostGo.GetComponent<LayoutElement>();
            hostLe.minHeight = 240f;
            hostLe.preferredHeight = 400f;
            hostLe.flexibleHeight = 1f;
            hostLe.flexibleWidth = 1f;

            var padGo = new GameObject("SketchPad", typeof(RectTransform), typeof(RawImage), typeof(UiSketchPad),
                typeof(AspectRatioFitter));
            padGo.transform.SetParent(hostGo.transform, false);
            var padRt = padGo.GetComponent<RectTransform>();
            padRt.anchorMin = new Vector2(0.5f, 0.5f);
            padRt.anchorMax = new Vector2(0.5f, 0.5f);
            padRt.pivot = new Vector2(0.5f, 0.5f);
            padRt.sizeDelta = new Vector2(400f, 533f);
            _pad = padGo.GetComponent<UiSketchPad>();
            var fitter = padGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.FitInParent;
            fitter.aspectRatio = _pad.TextureAspect;
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
            FrUiFactory.AddButton(col, "Magic!", t, ContinueToEnhancement, FrButtonEmphasis.Primary);
            FrUiFactory.AddButton(col, "Import photo", t, () =>
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
            AddTightButton(row, "Girl", t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Female;
                ApplyCurrentFigure("Girl model — draw on top.");
            });
            AddTightButton(row, "Boy", t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Male;
                ApplyCurrentFigure("Boy model — draw on top.");
            });
            AddTightButton(row, "Photo…", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ImportSketch);
            });
            AddTightButton(row, "Blank", t, () =>
            {
                _pad.ClearReferenceToBlank();
                _hint.text = "Blank paper — draw freely.";
            });
            _dimRefBtn = AddTightButton(row, "Dim", t, ToggleReferenceDim);

            var poseRow = NewToolbarRow(col);
            for (var i = 0; i < SketchFigurePreferences.PoseCount; i++)
            {
                var pose = i;
                var label = SketchFigurePreferences.PoseLabel(pose);
                AddTightButton(poseRow, label, t, () =>
                {
                    SketchFigurePreferences.DefaultPoseIndex = pose;
                    var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Boy" : "Girl";
                    ApplyCurrentFigure($"{who} · {label} — draw on top.");
                });
            }
        }

        void ApplyCurrentFigure(string hint)
        {
            _pad.ApplyDefaultFigure(SketchFigurePreferences.DefaultTemplate,
                SketchFigurePreferences.DefaultPoseIndex);
            _hint.text = hint;
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
                txt.text = _refDimmed ? "Bright" : "Dim";
            _hint.text = _refDimmed ? "Model faded — easier to draw." : "Model bright.";
        }

        void BootstrapPadReference(SketchFigureTemplate? forcedFigure)
        {
            if (App == null)
                return;

            if (forcedFigure.HasValue)
                SketchFigurePreferences.DefaultTemplate = forcedFigure.Value;

            var pending = App.CreateDesign.PendingReferenceImagePath?.Trim();
            if (!string.IsNullOrEmpty(pending) && File.Exists(pending))
            {
                App.CreateDesign.PendingReferenceImagePath = "";
                if (_pad.TryLoadUnderlayFromFile(pending, out var err))
                    _hint.text = "Your photo is ready — draw on top.";
                else
                {
                    _hint.text = string.IsNullOrEmpty(err) ? "Could not load photo; using default model." : err;
                    ApplyCurrentFigure(_hint.text);
                }
            }
            else
            {
                var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Boy" : "Girl";
                var pose = SketchFigurePreferences.DefaultPoseIndex + 1;
                ApplyCurrentFigure($"{who} · pose {pose} — draw your design, then Magic!");
            }

            RefreshEraseButtonStyle();
        }

        protected override void OnShown(object? payload)
        {
            if (App == null)
                return;

            SketchFigureTemplate? forced = null;
            if (payload is SketchNavContext ctx && ctx.Figure.HasValue)
                forced = ctx.Figure;
            else if (payload is SketchFigureTemplate t)
                forced = t;

            if (!_padBootstrapped)
            {
                _padBootstrapped = true;
                BootstrapPadReference(forced);
                return;
            }

            if (forced.HasValue)
            {
                SketchFigurePreferences.DefaultTemplate = forced.Value;
                var who = forced.Value == SketchFigureTemplate.Male ? "Boy" : "Girl";
                var pose = SketchFigurePreferences.DefaultPoseIndex + 1;
                ApplyCurrentFigure($"{who} · pose {pose} — draw your design, then Magic!");
            }

            var pending = App.CreateDesign.PendingReferenceImagePath?.Trim();
            if (string.IsNullOrEmpty(pending))
                return;

            App.CreateDesign.PendingReferenceImagePath = "";
            if (!File.Exists(pending))
            {
                _hint.text = "Photo file is missing.";
                return;
            }

            if (_pad.TryLoadUnderlayFromFile(pending, out var err))
                _hint.text = "Photo loaded — draw on top.";
            else
                _hint.text = string.IsNullOrEmpty(err) ? "Could not load photo." : err;
        }

        void ContinueToEnhancement()
        {
            if (!_pad.HasInk())
            {
                _hint.text = "Draw a little first — then Magic can help.";
                return;
            }

            var path = _pad.SavePngToPersistentData("canvas");
            App.CreateDesign.SketchReference = "file:" + path.Replace('\\', '/');
            _hint.text = " ";
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement,
                    new SketchNavContext { AutoMagic = true });
        }
    }
}
