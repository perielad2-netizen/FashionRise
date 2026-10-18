using System.IO;
using FashionRise.Application;
using FashionRise.Content;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Presentation.Sketch;
using FashionRise.UI.Studio;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// VR1 Creator Studio shell around the existing dual-layer <see cref="UiSketchPad"/>.
    /// Magic still saves the composite PNG and navigates to SketchEnhancement.
    /// </summary>
    public sealed class SketchCanvasScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.SketchCanvas;

        enum ModelChoice
        {
            Female,
            Male,
            Custom,
            Blank
        }

        UiSketchPad _pad = null!;
        FashionRiseTheme _theme = null!;
        FrStudioResponsiveLayout _layout = null!;
        FrStudioTopBar _topBar = null!;
        FrStudioToolRail _rail = null!;
        FrStudioInspector _inspector = null!;
        FrStudioAiButton _magic = null!;
        FrStudioCard _femaleCard = null!;
        FrStudioCard _maleCard = null!;
        FrStudioCard _customCard = null!;
        FrStudioCard _blankCard = null!;
        FrStudioIconButton _thin = null!;
        FrStudioIconButton _med = null!;
        FrStudioIconButton _thick = null!;
        FrStudioIconButton _bold = null!;
        FrStudioIconButton _dim = null!;
        readonly FrStudioIconButton[] _swatches = new FrStudioIconButton[4];
        readonly Color[] _inks =
        {
            new(0.11f, 0.09f, 0.08f),
            new(0.14f, 0.22f, 0.52f),
            new(0.62f, 0.12f, 0.18f),
            new(0.42f, 0.40f, 0.38f)
        };

        FrStudioOrientationStack _models = null!;
        bool _refDimmed;
        bool _padBootstrapped;
        bool _wide = true;
        ModelChoice _model = ModelChoice.Female;

        void Awake()
        {
            _theme = ThemeOrDefault;
            var shell = FrStudioShell.Build(transform, _theme);
            _topBar = FrStudioTopBar.Build(shell.TopSlot, _theme, GoBack, ImportSketch, OpenProfile);
            _layout = FrStudioResponsiveLayout.Build(shell.BodySlot, _theme);
            BuildModelColumn(_layout.LeftPanel);
            _rail = FrStudioToolRail.Build(_layout.ToolRail, _theme, () => SetInk(_pad.BrushColor, false),
                () => SetInk(default, true), UndoStroke, ClearDrawing);
            BuildCanvas(_layout.CanvasHost);
            _inspector = FrStudioInspector.Build(_layout.Inspector, _theme);
            BuildInspectorBody();
            _magic = FrStudioAiButton.Build(_inspector.Footer, _theme, ContinueToEnhancement);
            _wide = _layout.IsWide;
            ApplyChromeOrientation(!_wide);
            SelectBrushChip(5);
            SelectInk(0, apply: false);
        }

        void Update()
        {
            _layout.RefreshIfNeeded();
            if (_wide == _layout.IsWide)
                return;
            _wide = _layout.IsWide;
            ApplyChromeOrientation(!_wide);
        }

        void BuildModelColumn(Transform parent)
        {
            _models = FrStudioOrientationStack.Create(parent, "Models", _theme.SpaceSm, _theme.SpaceXs,
                TextAnchor.UpperCenter, TextAnchor.MiddleCenter, new RectOffset(4, 4, 6, 6));
            _models.Root.offsetMin = new Vector2(12f, 12f);
            _models.Root.offsetMax = new Vector2(-12f, -12f);

            var headHost = new GameObject("Head", typeof(RectTransform), typeof(LayoutElement));
            headHost.GetComponent<LayoutElement>().minHeight = 24f;
            var modelsHeading = FrStudioTypography.AddLabel(headHost.transform, "H", "MODELS", _theme,
                FrStudioTypeStyle.Metadata, muted: true, TextAnchor.MiddleLeft);
            FrStudioTypography.SetColor(modelsHeading,
                new Color(_theme.AccentMuted.r, _theme.AccentMuted.g, _theme.AccentMuted.b, 0.95f));

            // Card artwork from FashionRise model-selector sheet (runtime chrome handles selection).
            // Sketch pad underlay still uses SketchReference/* via UiSketchPad — unchanged.
            _femaleCard = FrStudioCard.Build(_models.Content, _theme, "Female", () => ApplyModel(ModelChoice.Female),
                FrStudioAssets.ModelFemale);
            _maleCard = FrStudioCard.Build(_models.Content, _theme, "Male", () => ApplyModel(ModelChoice.Male),
                FrStudioAssets.ModelMale);
            _customCard = FrStudioCard.Build(_models.Content, _theme, "Custom photo", ImportSketch,
                FrStudioAssets.ModelCustom);
            _blankCard = FrStudioCard.Build(_models.Content, _theme, "Blank paper",
                () => ApplyModel(ModelChoice.Blank), FrStudioAssets.ModelBlank);
            _models.Add(headHost.transform);
            _models.Add(_femaleCard.transform);
            _models.Add(_maleCard.transform);
            _models.Add(_customCard.transform);
            _models.Add(_blankCard.transform);
            SelectModelCard(ModelChoice.Female);
        }

        void BuildCanvas(Transform parent)
        {
            var inset = FashionRise.Config.DeviceLayoutPolicy.StudioCanvasInset;
            var frame = new GameObject("CanvasFrame", typeof(RectTransform), typeof(Image));
            var frameRt = frame.GetComponent<RectTransform>();
            frameRt.SetParent(parent, false);
            frameRt.anchorMin = Vector2.zero;
            frameRt.anchorMax = Vector2.one;
            frameRt.offsetMin = new Vector2(inset, inset);
            frameRt.offsetMax = new Vector2(-inset, -inset);
            var frameImg = frame.GetComponent<Image>();
            frameImg.sprite = FrStudioSprites.Rounded(80, Mathf.RoundToInt(_theme.CornerRadiusLarge), Color.white);
            frameImg.type = Image.Type.Sliced;
            frameImg.color = _theme.CanvasWell;
            frameImg.raycastTarget = false;
            var frameOutline = frame.AddComponent<Outline>();
            frameOutline.effectColor = new Color(_theme.AccentMuted.r, _theme.AccentMuted.g, _theme.AccentMuted.b, 0.85f);
            frameOutline.effectDistance = new Vector2(2f, -2f);
            var frameShade = frame.AddComponent<Shadow>();
            frameShade.effectColor = new Color(0f, 0f, 0f, 0.3f);
            frameShade.effectDistance = new Vector2(0f, -12f);
            frame.AddComponent<RectMask2D>();

            var padGo = new GameObject("SketchPad", typeof(RectTransform), typeof(RawImage), typeof(UiSketchPad),
                typeof(AspectRatioFitter));
            padGo.transform.SetParent(frame.transform, false);
            var padRt = padGo.GetComponent<RectTransform>();
            padRt.anchorMin = Vector2.zero;
            padRt.anchorMax = Vector2.one;
            padRt.offsetMin = new Vector2(22f, 22f);
            padRt.offsetMax = new Vector2(-22f, -22f);
            var fitter = padGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.FitInParent;
            fitter.aspectRatio = 768f / 1024f;
            _pad = padGo.GetComponent<UiSketchPad>();
            var rim = padGo.GetComponent<RawImage>();
            rim.raycastTarget = true;
            rim.color = Color.white;
        }

        void BuildInspectorBody()
        {
            var brush = FrStudioSection.Build(_inspector.ScrollBody, _theme, "Brush");
            var brushRow = NewChipRow(brush.Body, 52f);
            _thin = FrStudioIconButton.Chip(brushRow, _theme, "Thin", () => SetRadius(2));
            _med = FrStudioIconButton.Chip(brushRow, _theme, "Med", () => SetRadius(5));
            _thick = FrStudioIconButton.Chip(brushRow, _theme, "Thick", () => SetRadius(10));
            _bold = FrStudioIconButton.Chip(brushRow, _theme, "Bold", () => SetRadius(18));

            var color = FrStudioSection.Build(_inspector.ScrollBody, _theme, "Color");
            var colorRow = NewChipRow(color.Body, 64f);
            for (var i = 0; i < _inks.Length; i++)
            {
                var index = i;
                _swatches[i] = FrStudioIconButton.Swatch(colorRow, _theme, _inks[i], () => SelectInk(index, apply: true));
            }

            var reference = FrStudioSection.Build(_inspector.ScrollBody, _theme, "Reference");
            _dim = FrStudioIconButton.Chip(reference.Body, _theme, "Dim reference", ToggleReferenceDim);
            _inspector.SetStatus("Draw on the croquis, then Magic.");
        }

        static Transform NewChipRow(Transform parent, float minHeight)
        {
            var go = new GameObject("ChipRow", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            go.GetComponent<LayoutElement>().minHeight = minHeight;
            var h = go.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 10f;
            h.childAlignment = TextAnchor.MiddleCenter;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandWidth = true;
            h.childForceExpandHeight = false;
            return go.transform;
        }

        void ApplyChromeOrientation(bool compact)
        {
            _rail.SetHorizontal(compact);
            _models.SetHorizontal(compact);
        }

        void ApplyModel(ModelChoice choice)
        {
            _model = choice;
            switch (choice)
            {
                case ModelChoice.Female:
                    SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Female;
                    _pad.ApplyDefaultFigure(SketchFigureTemplate.Female);
                    SetStatus("Female model — draw on top.");
                    break;
                case ModelChoice.Male:
                    SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Male;
                    _pad.ApplyDefaultFigure(SketchFigureTemplate.Male);
                    SetStatus("Male model — draw on top.");
                    break;
                case ModelChoice.Blank:
                    _pad.ClearReferenceToBlank();
                    SetStatus("White reference — draw freely.");
                    break;
            }

            SelectModelCard(choice);
        }

        void SelectModelCard(ModelChoice choice)
        {
            _femaleCard.Selected = choice == ModelChoice.Female;
            _maleCard.Selected = choice == ModelChoice.Male;
            _customCard.Selected = choice == ModelChoice.Custom;
            _blankCard.Selected = choice == ModelChoice.Blank;
        }

        void SetRadius(int r)
        {
            _pad.SetBrushRadius(r);
            _pad.EraserActive = false;
            _rail.SetDrawSelected(true);
            SelectBrushChip(r);
            SetStatus($"Brush size {r}px.");
        }

        void SelectBrushChip(int r)
        {
            _thin.Selected = r == 2;
            _med.Selected = r == 5;
            _thick.Selected = r == 10;
            _bold.Selected = r == 18;
        }

        void SelectInk(int index, bool apply)
        {
            if (apply)
                SetInk(_inks[index], false);
            for (var i = 0; i < _swatches.Length; i++)
            {
                if (_swatches[i] != null)
                    _swatches[i].Selected = i == index;
            }
        }

        void SetInk(Color c, bool eraser)
        {
            if (!eraser)
                _pad.SetBrushColor(c);
            _pad.EraserActive = eraser;
            _rail.SetDrawSelected(!eraser);
            SetStatus(eraser ? "Eraser — remove ink only." : "Brush.");
        }

        void ToggleReferenceDim()
        {
            _refDimmed = !_refDimmed;
            _pad.ReferenceStrength = _refDimmed ? 0.4f : 1f;
            _pad.RefreshComposite();
            _dim.Selected = _refDimmed;
            SetStatus(_refDimmed ? "Reference dimmed for easier tracing." : "Reference at full strength.");
        }

        void UndoStroke()
        {
            if (!_pad.UndoStroke())
                SetStatus("Nothing to undo.");
            else
                SetStatus(" ");
        }

        void ClearDrawing()
        {
            _pad.ClearAll();
            SetStatus("Drawing cleared; reference unchanged.");
        }

        void GoBack()
        {
            if (App.Navigation != null)
                _ = App.Navigation.GoBackAsync();
        }

        void ImportSketch()
        {
            _model = ModelChoice.Custom;
            SelectModelCard(ModelChoice.Custom);
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.ImportSketch);
        }

        void OpenProfile()
        {
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.Profile);
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
                {
                    _model = ModelChoice.Custom;
                    SelectModelCard(ModelChoice.Custom);
                    SetStatus("Custom reference loaded — draw on top.");
                }
                else
                {
                    SetStatus(string.IsNullOrEmpty(err) ? "Could not load reference; using default model." : err);
                    ApplyPreferredFigure();
                }
            }
            else
            {
                ApplyPreferredFigure();
                SetStatus("Default model — switch Female/Male, dim the reference, or import a photo.");
            }

            _rail.SetDrawSelected(!_pad.EraserActive);
            _topBar.RefreshAutosave();
        }

        void ApplyPreferredFigure()
        {
            var preferred = SketchFigurePreferences.DefaultTemplate;
            _model = preferred == SketchFigureTemplate.Male ? ModelChoice.Male : ModelChoice.Female;
            _pad.ApplyDefaultFigure(preferred);
            SelectModelCard(_model);
        }

        protected override void OnShown(object? payload)
        {
            if (App == null)
                return;

            _topBar.RefreshAutosave();
            _layout.Apply(force: true);
            _wide = _layout.IsWide;
            ApplyChromeOrientation(!_wide);

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
                SetStatus("Reference file is missing.");
                return;
            }

            if (_pad.TryLoadUnderlayFromFile(pending, out var err))
            {
                _model = ModelChoice.Custom;
                SelectModelCard(ModelChoice.Custom);
                SetStatus("Reference loaded — draw on top.");
            }
            else
                SetStatus(string.IsNullOrEmpty(err) ? "Could not load reference." : err);
        }

        void ContinueToEnhancement()
        {
            if (!_pad.HasInk())
            {
                SetStatus("Draw on the canvas first (ink on croquis, photo, or blank paper).");
                return;
            }

            var path = _pad.SavePngToPersistentData("canvas");
            App.CreateDesign.SketchReference = "file:" + path.Replace('\\', '/');
            SetStatus(" ");
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement);
        }

        void SetStatus(string text) => _inspector.SetStatus(text);
    }
}
