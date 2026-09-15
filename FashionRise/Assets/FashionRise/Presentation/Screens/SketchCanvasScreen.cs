using System.IO;
using FashionRise.Application;
using FashionRise.Content;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Presentation.Sketch;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Kid fashion studio: full-height mannequin, brush tools left, colors/fabrics right.
    /// Draw → MAGIC! — not a wall of category buttons.
    /// </summary>
    public sealed class SketchCanvasScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.SketchCanvas;

        UiSketchPad _pad = null!;
        Text _hint = null!;
        FashionRiseTheme _theme = null!;
        bool _padBootstrapped;
        bool _refDimmed;

        Button _pencilBtn = null!;
        Button _eraserBtn = null!;
        Image? _pencilFace;
        Image? _eraserFace;
        readonly Image[] _sizeFaces = new Image[3];
        readonly Image[] _sizeDots = new Image[3];
        readonly Image[] _colorFaces = new Image[8];
        readonly Image[] _fabricFaces = new Image[6];
        int _sizeIndex = 1;
        int _colorIndex;
        int _fabricIndex = -1;

        static readonly int[] BrushSizes = { 3, 9, 20 };

        static readonly Color[] InkColors =
        {
            new(0.10f, 0.08f, 0.08f),
            new(0.78f, 0.12f, 0.28f),
            new(0.12f, 0.28f, 0.62f),
            new(0.95f, 0.55f, 0.15f),
            new(0.20f, 0.55f, 0.38f),
            new(0.72f, 0.42f, 0.72f),
            new(0.95f, 0.92f, 0.88f),
            new(0.45f, 0.45f, 0.48f),
        };

        static readonly string[] ColorNames =
        {
            "Ink", "Rose", "Navy", "Gold", "Emerald", "Orchid", "Cream", "Grey"
        };

        static readonly (string name, Color color, int radius)[] Fabrics =
        {
            ("Silk", new Color(0.98f, 0.90f, 0.94f), 7),
            ("Denim", new Color(0.22f, 0.38f, 0.62f), 13),
            ("Velvet", new Color(0.45f, 0.08f, 0.22f), 15),
            ("Glitter", new Color(0.95f, 0.35f, 0.65f), 11),
            ("Leather", new Color(0.18f, 0.12f, 0.10f), 12),
            ("Cotton", new Color(0.92f, 0.94f, 0.98f), 9),
        };

        void Awake()
        {
            var t = ThemeOrDefault;
            _theme = t;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);

            BuildTopBar(root, t);
            BuildStudio(root, t);

            SelectPencil();
            SetSize(1);
            SetColor(0);
        }

        void BuildTopBar(RectTransform root, FashionRiseTheme t)
        {
            var top = new GameObject("TopBar", typeof(RectTransform), typeof(Image), typeof(HorizontalLayoutGroup));
            var topRt = top.GetComponent<RectTransform>();
            topRt.SetParent(root, false);
            topRt.anchorMin = new Vector2(0f, 1f);
            topRt.anchorMax = new Vector2(1f, 1f);
            topRt.pivot = new Vector2(0.5f, 1f);
            topRt.sizeDelta = new Vector2(0f, 72f);
            topRt.anchoredPosition = Vector2.zero;
            top.GetComponent<Image>().color = new Color(1f, 1f, 1f, 0.42f);
            var topH = top.GetComponent<HorizontalLayoutGroup>();
            topH.padding = new RectOffset(12, 12, 8, 8);
            topH.spacing = 10f;
            topH.childAlignment = TextAnchor.MiddleCenter;
            topH.childControlWidth = true;
            topH.childForceExpandWidth = false;
            topH.childControlHeight = true;
            topH.childForceExpandHeight = true;

            var back = FrUiFactory.AddButton(top.transform, "←", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
            ShrinkBarButton(back, 52f);

            _hint = FrUiFactory.AddLabel(top.transform, "Hint", "Pick a brush — draw your look", t,
                Mathf.RoundToInt(t.BodySize), FontStyle.Bold, TextAnchor.MiddleCenter);
            var hintLe = _hint.GetComponent<LayoutElement>() ?? _hint.gameObject.AddComponent<LayoutElement>();
            hintLe.flexibleWidth = 1f;
            hintLe.minHeight = 36f;

            var magic = FrUiFactory.AddButton(top.transform, "MAGIC!", t, ContinueToEnhancement,
                FrButtonEmphasis.Primary);
            ShrinkBarButton(magic, 132f);
            var magicMotion = magic.GetComponent<FrUiMotion>();
            if (magicMotion != null)
                magicMotion.EnablePulse(true);
        }

        void BuildStudio(RectTransform root, FashionRiseTheme t)
        {
            // Full-bleed stage: mannequin owns the height; tool rails float on each side.
            var studio = new GameObject("Studio", typeof(RectTransform));
            var studioRt = studio.GetComponent<RectTransform>();
            studioRt.SetParent(root, false);
            studioRt.anchorMin = Vector2.zero;
            studioRt.anchorMax = Vector2.one;
            studioRt.offsetMin = new Vector2(4f, 6f);
            studioRt.offsetMax = new Vector2(-4f, -76f);

            BuildMannequinStage(studioRt, t);
            // Rails after stage so they sit on top and receive taps
            BuildLeftRail(studioRt, t);
            BuildRightRail(studioRt, t);
        }

        void BuildLeftRail(RectTransform studio, FashionRiseTheme t)
        {
            var rail = MakeScrollRail(studio, "LeftRail", true, 100f, t);
            AddRailCaption(rail, "BRUSH", t);

            _pencilBtn = AddLabeledTool(rail, "Pencil", "Pencil", t, SelectPencil, out _pencilFace);
            _eraserBtn = AddLabeledTool(rail, "Eraser", "Eraser", t, SelectEraser, out _eraserFace);

            AddRailCaption(rail, "SIZE", t);
            for (var i = 0; i < 3; i++)
            {
                var idx = i;
                var dotPx = 10f + i * 10f;
                AddSizeTool(rail, idx, dotPx, t, () => SetSize(idx));
            }

            AddRailCaption(rail, "EDIT", t);
            AddLabeledTool(rail, "Undo", "Undo", t, () =>
            {
                if (!_pad.UndoStroke())
                    FlashHint("Nothing to undo");
                else
                    FlashHint("Undone!");
            }, out _);
            AddLabeledTool(rail, "Clear", "Clear", t, () =>
            {
                _pad.ClearAll();
                FlashHint("Fresh page");
            }, out _);
            AddLabeledTool(rail, "Fade", "Fade", t, ToggleReferenceDim, out _);
        }

        void BuildRightRail(RectTransform studio, FashionRiseTheme t)
        {
            var rail = MakeScrollRail(studio, "RightRail", false, 110f, t);

            AddRailCaption(rail, "COLOR", t);
            var colorGrid = MakeGrid(rail, "ColorGrid", 2, 6f);
            for (var i = 0; i < InkColors.Length; i++)
            {
                var idx = i;
                _colorFaces[i] = AddColorSwatch(colorGrid, InkColors[i], ColorNames[i], () =>
                {
                    _fabricIndex = -1;
                    ClearFabricSelection();
                    SetColor(idx);
                });
            }

            AddRailCaption(rail, "FABRIC", t);
            for (var i = 0; i < Fabrics.Length; i++)
            {
                var idx = i;
                _fabricFaces[i] = AddFabricTile(rail, Fabrics[i].name, Fabrics[i].color, () => SelectFabric(idx));
            }

            AddRailCaption(rail, "MODEL", t);
            AddLabeledTool(rail, "Girl", "Girl", t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Female;
                ApplyCurrentFigure("Girl model");
            }, out _);
            AddLabeledTool(rail, "Boy", "Boy", t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Male;
                ApplyCurrentFigure("Boy model");
            }, out _);
            AddLabeledTool(rail, "Photo", "Photo", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ImportSketch);
            }, out _);
            AddLabeledTool(rail, "Pose", "Pose", t, CyclePose, out _);
        }

        void BuildMannequinStage(RectTransform studio, FashionRiseTheme t)
        {
            var stage = new GameObject("MannequinStage", typeof(RectTransform), typeof(Image), typeof(RectMask2D));
            stage.transform.SetParent(studio, false);
            var stageRt = stage.GetComponent<RectTransform>();
            stageRt.anchorMin = Vector2.zero;
            stageRt.anchorMax = Vector2.one;
            stageRt.offsetMin = Vector2.zero;
            stageRt.offsetMax = Vector2.zero;
            var stageImg = stage.GetComponent<Image>();
            stageImg.color = new Color(1f, 1f, 1f, 0.5f);
            var outline = stage.AddComponent<Outline>();
            outline.effectColor = new Color(t.Champagne.r, t.Champagne.g, t.Champagne.b, 0.75f);
            outline.effectDistance = new Vector2(2.5f, -2.5f);
            var shadow = stage.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.25f, 0.1f, 0.16f, 0.2f);
            shadow.effectDistance = new Vector2(0f, -10f);

            var spot = new GameObject("Spotlight", typeof(RectTransform), typeof(Image));
            spot.transform.SetParent(stage.transform, false);
            var spotRt = spot.GetComponent<RectTransform>();
            spotRt.anchorMin = new Vector2(0.05f, 0.01f);
            spotRt.anchorMax = new Vector2(0.95f, 0.99f);
            spotRt.offsetMin = Vector2.zero;
            spotRt.offsetMax = Vector2.zero;
            var spotImg = spot.GetComponent<Image>();
            spotImg.color = new Color(t.Champagne.r, t.Champagne.g, t.Champagne.b, 0.3f);
            spotImg.raycastTarget = false;
            var spotMotion = spot.AddComponent<FrUiMotion>();
            spotMotion.EnablePulse(true);

            var padGo = new GameObject("SketchPad", typeof(RectTransform), typeof(RawImage), typeof(UiSketchPad),
                typeof(AspectRatioFitter));
            padGo.transform.SetParent(stage.transform, false);
            var padRt = padGo.GetComponent<RectTransform>();
            padRt.anchorMin = Vector2.zero;
            padRt.anchorMax = Vector2.one;
            padRt.offsetMin = Vector2.zero;
            padRt.offsetMax = Vector2.zero;
            _pad = padGo.GetComponent<UiSketchPad>();
            var fitter = padGo.GetComponent<AspectRatioFitter>();
            // Prefer full vertical fill on phone/tablet studio
            fitter.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth;
            fitter.aspectRatio = _pad.TextureAspect;
            var padMotionRt = padRt;
            padRt.anchorMin = new Vector2(0.5f, 0f);
            padRt.anchorMax = new Vector2(0.5f, 1f);
            padRt.pivot = new Vector2(0.5f, 0.5f);
            padRt.offsetMin = new Vector2(0f, 2f);
            padRt.offsetMax = new Vector2(0f, -2f);
            var rim = padGo.GetComponent<RawImage>();
            rim.raycastTarget = true;
            rim.color = Color.white;
        }

        static Transform MakeScrollRail(RectTransform parent, string name, bool left, float width, FashionRiseTheme t)
        {
            var shell = new GameObject(name, typeof(RectTransform), typeof(Image));
            shell.transform.SetParent(parent, false);
            var shellRt = shell.GetComponent<RectTransform>();
            if (left)
            {
                shellRt.anchorMin = new Vector2(0f, 0f);
                shellRt.anchorMax = new Vector2(0f, 1f);
                shellRt.pivot = new Vector2(0f, 0.5f);
                shellRt.sizeDelta = new Vector2(width, 0f);
                shellRt.anchoredPosition = new Vector2(0f, 0f);
            }
            else
            {
                shellRt.anchorMin = new Vector2(1f, 0f);
                shellRt.anchorMax = new Vector2(1f, 1f);
                shellRt.pivot = new Vector2(1f, 0.5f);
                shellRt.sizeDelta = new Vector2(width, 0f);
                shellRt.anchoredPosition = Vector2.zero;
            }

            shell.GetComponent<Image>().color = new Color(1f, 1f, 1f, 0.72f);
            var shellOutline = shell.AddComponent<Outline>();
            shellOutline.effectColor = new Color(t.AccentMuted.r, t.AccentMuted.g, t.AccentMuted.b, 0.45f);
            shellOutline.effectDistance = new Vector2(1.5f, -1.5f);
            var shellShadow = shell.AddComponent<Shadow>();
            shellShadow.effectColor = new Color(0.2f, 0.08f, 0.14f, 0.16f);
            shellShadow.effectDistance = new Vector2(left ? 4f : -4f, -4f);

            var scrollGo = new GameObject("Scroll", typeof(RectTransform), typeof(ScrollRect), typeof(Image));
            scrollGo.transform.SetParent(shell.transform, false);
            var scrollRt = scrollGo.GetComponent<RectTransform>();
            scrollRt.anchorMin = Vector2.zero;
            scrollRt.anchorMax = Vector2.one;
            scrollRt.offsetMin = new Vector2(4f, 4f);
            scrollRt.offsetMax = new Vector2(-4f, -4f);
            scrollGo.GetComponent<Image>().color = new Color(1f, 1f, 1f, 0.01f);
            scrollGo.GetComponent<Image>().raycastTarget = true;

            var content = new GameObject("Content", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(ContentSizeFitter));
            content.transform.SetParent(scrollGo.transform, false);
            var contentRt = content.GetComponent<RectTransform>();
            contentRt.anchorMin = new Vector2(0f, 1f);
            contentRt.anchorMax = new Vector2(1f, 1f);
            contentRt.pivot = new Vector2(0.5f, 1f);
            contentRt.anchoredPosition = Vector2.zero;
            contentRt.sizeDelta = new Vector2(0f, 0f);
            var v = content.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(6, 6, 8, 12);
            v.spacing = 6f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;
            var fit = content.GetComponent<ContentSizeFitter>();
            fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            fit.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;

            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.content = contentRt;
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Clamped;
            scroll.scrollSensitivity = 28f;
            scroll.viewport = scrollRt;

            return content.transform;
        }

        static Transform MakeGrid(Transform parent, string name, int columns, float spacing)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(GridLayoutGroup), typeof(LayoutElement),
                typeof(ContentSizeFitter));
            go.transform.SetParent(parent, false);
            var grid = go.GetComponent<GridLayoutGroup>();
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = columns;
            grid.cellSize = new Vector2(48f, 48f);
            grid.spacing = new Vector2(spacing, spacing);
            grid.childAlignment = TextAnchor.UpperCenter;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 110f;
            le.preferredHeight = 110f;
            le.flexibleWidth = 1f;
            var fit = go.GetComponent<ContentSizeFitter>();
            fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            return go.transform;
        }

        static void AddRailCaption(Transform rail, string text, FashionRiseTheme t)
        {
            var label = FrUiFactory.AddLabel(rail, text, text, t, Mathf.RoundToInt(t.CaptionSize), FontStyle.Bold,
                TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var le = label.GetComponent<LayoutElement>() ?? label.gameObject.AddComponent<LayoutElement>();
            le.minHeight = 16f;
            le.preferredHeight = 18f;
        }

        Button AddLabeledTool(Transform parent, string name, string label, FashionRiseTheme t, UnityAction onClick,
            out Image face)
        {
            var go = new GameObject(name + "_Tool", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            face = go.GetComponent<Image>();
            face.color = t.ButtonFace;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 48f;
            le.preferredHeight = 50f;
            le.flexibleWidth = 1f;
            var outline = go.AddComponent<Outline>();
            outline.effectColor = new Color(t.AccentMuted.r, t.AccentMuted.g, t.AccentMuted.b, 0.5f);
            outline.effectDistance = new Vector2(1.2f, -1.2f);

            var txtGo = new GameObject("Label", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            txt.text = label;
            txt.fontSize = 15;
            txt.fontStyle = FontStyle.Bold;
            txt.alignment = TextAnchor.MiddleCenter;
            txt.color = t.MidnightNavy;
            txt.raycastTarget = false;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = Vector2.zero;
            trt.offsetMax = Vector2.zero;

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            HookPress(go, go.AddComponent<FrUiMotion>());
            return btn;
        }

        void AddSizeTool(Transform parent, int index, float dotPx, FashionRiseTheme t, UnityAction onClick)
        {
            var go = new GameObject("Size" + index, typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.color = t.ButtonFace;
            _sizeFaces[index] = face;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 44f;
            le.preferredHeight = 46f;
            le.flexibleWidth = 1f;
            go.AddComponent<Outline>().effectColor = new Color(t.AccentMuted.r, t.AccentMuted.g, t.AccentMuted.b, 0.4f);

            var dot = new GameObject("Dot", typeof(Image));
            dot.transform.SetParent(go.transform, false);
            var dotImg = dot.GetComponent<Image>();
            dotImg.color = t.MidnightNavy;
            dotImg.raycastTarget = false;
            _sizeDots[index] = dotImg;
            var drt = dot.GetComponent<RectTransform>();
            drt.anchorMin = new Vector2(0.5f, 0.5f);
            drt.anchorMax = new Vector2(0.5f, 0.5f);
            drt.sizeDelta = new Vector2(dotPx, dotPx);

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            HookPress(go, go.AddComponent<FrUiMotion>());
        }

        Image AddColorSwatch(Transform parent, Color color, string tip, UnityAction onClick)
        {
            var go = new GameObject(tip + "_Color", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.color = color;
            var outline = go.AddComponent<Outline>();
            outline.effectColor = new Color(0.2f, 0.1f, 0.15f, 0.4f);
            outline.effectDistance = new Vector2(1.5f, -1.5f);
            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            HookPress(go, go.AddComponent<FrUiMotion>());
            return face;
        }

        Image AddFabricTile(Transform parent, string name, Color color, UnityAction onClick)
        {
            var go = new GameObject(name + "_Fabric", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.color = color;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 42f;
            le.preferredHeight = 44f;
            le.flexibleWidth = 1f;
            var outline = go.AddComponent<Outline>();
            outline.effectColor = new Color(0.2f, 0.1f, 0.15f, 0.35f);
            outline.effectDistance = new Vector2(1.5f, -1.5f);

            var txtGo = new GameObject("Name", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            txt.text = name;
            txt.fontSize = 13;
            txt.fontStyle = FontStyle.Bold;
            txt.alignment = TextAnchor.MiddleCenter;
            // Dark fabrics get light text
            var lum = color.r * 0.3f + color.g * 0.59f + color.b * 0.11f;
            txt.color = lum < 0.45f ? Color.white : new Color(0.15f, 0.1f, 0.14f, 1f);
            txt.raycastTarget = false;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = Vector2.zero;
            trt.offsetMax = Vector2.zero;

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            HookPress(go, go.AddComponent<FrUiMotion>());
            return face;
        }

        static void HookPress(GameObject go, FrUiMotion motion)
        {
            var trigger = go.AddComponent<EventTrigger>();
            void Hook(EventTriggerType type, UnityAction<BaseEventData> cb)
            {
                var e = new EventTrigger.Entry { eventID = type };
                e.callback.AddListener(cb);
                trigger.triggers.Add(e);
            }

            Hook(EventTriggerType.PointerDown, _ => motion.SetPressed(true));
            Hook(EventTriggerType.PointerUp, _ => motion.SetPressed(false));
            Hook(EventTriggerType.PointerExit, _ => motion.SetPressed(false));
        }

        static void ShrinkBarButton(Button btn, float width)
        {
            var le = btn.GetComponent<LayoutElement>();
            if (le == null)
                return;
            le.flexibleWidth = 0f;
            le.minWidth = width;
            le.preferredWidth = width;
            le.minHeight = 48f;
            le.preferredHeight = 48f;
        }

        void SelectPencil()
        {
            _pad.EraserActive = false;
            if (_fabricIndex >= 0)
                ApplyFabricBrush(_fabricIndex);
            else
            {
                _pad.SetBrushColor(InkColors[_colorIndex]);
                _pad.SetBrushRadius(BrushSizes[_sizeIndex]);
            }

            HighlightTool(true);
            FlashHint("Pencil — draw clothes!");
        }

        void SelectEraser()
        {
            _pad.EraserActive = true;
            HighlightTool(false);
            FlashHint("Eraser — rub to erase");
        }

        void SetSize(int index)
        {
            _sizeIndex = Mathf.Clamp(index, 0, BrushSizes.Length - 1);
            if (_fabricIndex < 0 || _pad.EraserActive)
                _pad.SetBrushRadius(BrushSizes[_sizeIndex]);
            else
                _pad.SetBrushRadius(BrushSizes[_sizeIndex]);

            if (!_pad.EraserActive)
                HighlightTool(true);

            for (var i = 0; i < _sizeFaces.Length; i++)
            {
                if (_sizeFaces[i] != null)
                    _sizeFaces[i].color = i == _sizeIndex ? _theme.AccentMuted : _theme.ButtonFace;
                if (_sizeDots[i] != null)
                    _sizeDots[i].color = i == _sizeIndex ? _theme.Accent : _theme.MidnightNavy;
            }

            FlashHint(_sizeIndex == 0 ? "Thin pencil" : _sizeIndex == 1 ? "Medium brush" : "Bold brush");
        }

        void SetColor(int index)
        {
            _colorIndex = Mathf.Clamp(index, 0, InkColors.Length - 1);
            _pad.SetBrushColor(InkColors[_colorIndex]);
            _pad.SetBrushRadius(BrushSizes[_sizeIndex]);
            _pad.EraserActive = false;
            HighlightTool(true);
            for (var i = 0; i < _colorFaces.Length; i++)
            {
                if (_colorFaces[i] == null)
                    continue;
                var o = _colorFaces[i].GetComponent<Outline>();
                if (o == null)
                    continue;
                o.effectDistance = i == _colorIndex ? new Vector2(3.5f, -3.5f) : new Vector2(1.5f, -1.5f);
                o.effectColor = i == _colorIndex
                    ? new Color(_theme.Accent.r, _theme.Accent.g, _theme.Accent.b, 0.95f)
                    : new Color(0.2f, 0.1f, 0.15f, 0.4f);
            }

            FlashHint(ColorNames[_colorIndex] + " ready");
        }

        void SelectFabric(int index)
        {
            _fabricIndex = Mathf.Clamp(index, 0, Fabrics.Length - 1);
            ApplyFabricBrush(_fabricIndex);
            _pad.EraserActive = false;
            HighlightTool(true);
            ClearFabricSelection();
            if (_fabricFaces[_fabricIndex] != null)
            {
                var o = _fabricFaces[_fabricIndex].GetComponent<Outline>();
                if (o != null)
                {
                    o.effectDistance = new Vector2(3.5f, -3.5f);
                    o.effectColor = new Color(_theme.Accent.r, _theme.Accent.g, _theme.Accent.b, 0.95f);
                }
            }

            FlashHint(Fabrics[_fabricIndex].name + " fabric");
        }

        void ApplyFabricBrush(int index)
        {
            var f = Fabrics[index];
            _pad.SetBrushColor(f.color);
            _pad.SetBrushRadius(f.radius);
            _sizeIndex = f.radius <= 8 ? 0 : f.radius <= 13 ? 1 : 2;
            for (var i = 0; i < _sizeFaces.Length; i++)
            {
                if (_sizeFaces[i] != null)
                    _sizeFaces[i].color = i == _sizeIndex ? _theme.AccentMuted : _theme.ButtonFace;
                if (_sizeDots[i] != null)
                    _sizeDots[i].color = i == _sizeIndex ? _theme.Accent : _theme.MidnightNavy;
            }
        }

        void ClearFabricSelection()
        {
            for (var i = 0; i < _fabricFaces.Length; i++)
            {
                if (_fabricFaces[i] == null)
                    continue;
                var o = _fabricFaces[i].GetComponent<Outline>();
                if (o == null)
                    continue;
                o.effectDistance = new Vector2(1.5f, -1.5f);
                o.effectColor = new Color(0.2f, 0.1f, 0.15f, 0.35f);
            }
        }

        void HighlightTool(bool pencil)
        {
            if (_pencilFace != null)
                _pencilFace.color = pencil ? _theme.Accent : _theme.ButtonFace;
            if (_eraserFace != null)
                _eraserFace.color = pencil ? _theme.ButtonFace : new Color(0.95f, 0.78f, 0.82f, 1f);
            var pTxt = _pencilBtn != null ? _pencilBtn.GetComponentInChildren<Text>() : null;
            var eTxt = _eraserBtn != null ? _eraserBtn.GetComponentInChildren<Text>() : null;
            if (pTxt != null)
                pTxt.color = pencil ? Color.white : _theme.MidnightNavy;
            if (eTxt != null)
                eTxt.color = pencil ? _theme.MidnightNavy : _theme.MidnightNavy;
        }

        void CyclePose()
        {
            var next = (SketchFigurePreferences.DefaultPoseIndex + 1) % SketchFigurePreferences.PoseCount;
            SketchFigurePreferences.DefaultPoseIndex = next;
            var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Boy" : "Girl";
            ApplyCurrentFigure($"{who} · {SketchFigurePreferences.PoseLabel(next)}");
        }

        void FlashHint(string msg)
        {
            if (_hint != null)
                _hint.text = msg;
        }

        void ApplyCurrentFigure(string hint)
        {
            _pad.ApplyDefaultFigure(SketchFigurePreferences.DefaultTemplate,
                SketchFigurePreferences.DefaultPoseIndex);
            FlashHint(hint);
        }

        void ToggleReferenceDim()
        {
            _refDimmed = !_refDimmed;
            _pad.ReferenceStrength = _refDimmed ? 0.4f : 1f;
            _pad.RefreshComposite();
            FlashHint(_refDimmed ? "Model faded — easier to draw" : "Model bright");
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
                    FlashHint("Photo ready — draw!");
                else
                {
                    FlashHint(string.IsNullOrEmpty(err) ? "Using default model" : err);
                    ApplyCurrentFigure(_hint.text);
                }
            }
            else
            {
                var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Boy" : "Girl";
                ApplyCurrentFigure($"{who} — draw your look!");
            }
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
                ApplyCurrentFigure($"{who} — draw your look!");
            }

            var pending = App.CreateDesign.PendingReferenceImagePath?.Trim();
            if (string.IsNullOrEmpty(pending))
                return;

            App.CreateDesign.PendingReferenceImagePath = "";
            if (!File.Exists(pending))
            {
                FlashHint("Photo missing");
                return;
            }

            if (_pad.TryLoadUnderlayFromFile(pending, out var err))
                FlashHint("Photo ready — draw!");
            else
                FlashHint(string.IsNullOrEmpty(err) ? "Could not load photo" : err);
        }

        void ContinueToEnhancement()
        {
            if (!_pad.HasInk())
            {
                FlashHint("Draw a little first!");
                return;
            }

            var path = _pad.SavePngToPersistentData("canvas");
            App.CreateDesign.SketchReference = "file:" + path.Replace('\\', '/');
            FlashHint("Magic…");
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement,
                    new SketchNavContext { AutoMagic = true });
        }
    }
}
