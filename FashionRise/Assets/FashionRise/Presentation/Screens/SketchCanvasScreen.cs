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
            headHost.GetComponent<LayoutElement>().minHeight = 22f;
            FrStudioTypography.AddLabel(headHost.transform, "H", "Models", _theme, FrStudioTypeStyle.Metadata,
                muted: true, TextAnchor.MiddleLeft);

            var femaleTex = Resources.Load<Texture2D>("SketchReference/female_model");
            var maleTex = Resources.Load<Texture2D>("SketchReference/male_model");
            _femaleCard = FrStudioCard.Build(_models.Content, _theme, "Female", () => ApplyModel(ModelChoice.Female),
                femaleTex);
            _maleCard = FrStudioCard.Build(_models.Content, _theme, "Male", () => ApplyModel(ModelChoice.Male),
                maleTex);
            _customCard = FrStudioCard.Build(_models.Content, _theme, "Custom photo", ImportSketch);
            _blankCard = FrStudioCard.Build(_models.Content, _theme, "Blank paper", () => ApplyModel(ModelChoice.Blank));
            _models.Add(headHost.transform);
            _models.Add(_femaleCard.transform);
            _models.Add(_maleCard.transform);
            _models.Add(_customCard.transform);
            _models.Add(_blankCard.transform);
            SelectModelCard(ModelChoice.Female);
        }

        void BuildCanvas(Transform parent)
        {
            var well = new GameObject("CanvasWell", typeof(RectTransform), typeof(Image));
            var wellRt = well.GetComponent<RectTransform>();
            wellRt.SetParent(parent, false);
            wellRt.anchorMin = Vector2.zero;
            wellRt.anchorMax = Vector2.one;
            wellRt.offsetMin = new Vector2(18f, 18f);
            wellRt.offsetMax = new Vector2(-18f, -18f);
            var wellImg = well.GetComponent<Image>();
            wellImg.sprite = FrStudioSprites.Rounded(64, Mathf.RoundToInt(_theme.CornerRadiusLarge), Color.white);
            wellImg.type = Image.Type.Sliced;
            wellImg.color = _theme.CanvasWell;
            wellImg.raycastTarget = false;
            well.AddComponent<RectMask2D>();
            var shade = well.AddComponent<Shadow>();
            shade.effectColor = _theme.Shadow;
            shade.effectDistance = new Vector2(0f, -6f);

            var padGo = new GameObject("SketchPad", typeof(RectTransform), typeof(RawImage), typeof(UiSketchPad),
                typeof(AspectRatioFitter));
            padGo.transform.SetParent(well.transform, false);
            var padRt = padGo.GetComponent<RectTransform>();
            padRt.anchorMin = Vector2.zero;
            padRt.anchorMax = Vector2.one;
            padRt.offsetMin = new Vector2(16f, 16f);
            padRt.offsetMax = new Vector2(-16f, -16f);
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
            var brushRow = NewChipRow(brush.Body);
            _thin = FrStudioIconButton.Chip(brushRow, _theme, "Thin", () => SetRadius(2));
            _med = FrStudioIconButton.Chip(brushRow, _theme, "Med", () => SetRadius(5));
            _thick = FrStudioIconButton.Chip(brushRow, _theme, "Thick", () => SetRadius(10));
            _bold = FrStudioIconButton.Chip(brushRow, _theme, "Bold", () => SetRadius(18));

            var color = FrStudioSection.Build(_inspector.ScrollBody, _theme, "Color");
            var colorRow = NewChipRow(color.Body);
            for (var i = 0; i < _inks.Length; i++)
            {
                var index = i;
                _swatches[i] = FrStudioIconButton.Swatch(colorRow, _theme, _inks[i], () => SelectInk(index, apply: true));
            }

            var reference = FrStudioSection.Build(_inspector.ScrollBody, _theme, "Reference");
            _dim = FrStudioIconButton.Chip(reference.Body, _theme, "Dim reference", ToggleReferenceDim);
            _inspector.SetStatus("Draw on the croquis, then Magic.");
        }

        static Transform NewChipRow(Transform parent)
        {
            var go = new GameObject("ChipRow", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            go.GetComponent<LayoutElement>().minHeight = 48f;
            var h = go.GetComponent<HorizontalLayoutGroup>();
            h.spacing = 8f;
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
