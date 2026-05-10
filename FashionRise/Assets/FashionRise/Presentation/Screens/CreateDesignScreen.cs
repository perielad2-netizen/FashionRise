using System.Linq;
using System.Threading.Tasks;
using FashionRise.Application;
using FashionRise.Core;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class CreateDesignScreen : ScreenBase
    {
        Text _summary = null!;

        public override ScreenId Id => ScreenId.CreateDesign;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Create design", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _summary = FrUiFactory.AddLabel(col, "Sum", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);

            FrUiFactory.AddButton(col, "Category -> next", t,
                () => { App.CreateDesign.Category = EnumCycle.Next(App.CreateDesign.Category); Refresh(); });
            FrUiFactory.AddButton(col, "Template -> next in category", t, () => { _ = CycleTemplateAsync(); });
            FrUiFactory.AddButton(col, "Neckline -> next", t,
                () => { App.CreateDesign.Neckline = EnumCycle.Next(App.CreateDesign.Neckline); Refresh(); });
            FrUiFactory.AddButton(col, "Sleeve -> next", t,
                () => { App.CreateDesign.Sleeve = EnumCycle.Next(App.CreateDesign.Sleeve); Refresh(); });
            FrUiFactory.AddButton(col, "Length -> next", t,
                () => { App.CreateDesign.Length = EnumCycle.Next(App.CreateDesign.Length); Refresh(); });
            FrUiFactory.AddButton(col, "Fit -> next", t,
                () => { App.CreateDesign.Fit = EnumCycle.Next(App.CreateDesign.Fit); Refresh(); });
            FrUiFactory.AddButton(col, "Waist -> next", t,
                () => { App.CreateDesign.Waist = EnumCycle.Next(App.CreateDesign.Waist); Refresh(); });
            FrUiFactory.AddButton(col, "Silhouette volume (V2)", t,
                () =>
                {
                    App.CreateDesign.SilhouetteVolume = EnumCycle.Next(App.CreateDesign.SilhouetteVolume);
                    Refresh();
                });
            FrUiFactory.AddButton(col, "Drape expression (V2)", t,
                () =>
                {
                    App.CreateDesign.DrapeExpression = EnumCycle.Next(App.CreateDesign.DrapeExpression);
                    Refresh();
                });
            FrUiFactory.AddButton(col, "Layering depth (V2)", t,
                () =>
                {
                    App.CreateDesign.LayeringDepth = EnumCycle.Next(App.CreateDesign.LayeringDepth);
                    Refresh();
                });
            FrUiFactory.AddButton(col, "Seam accent (V2)", t,
                () => { App.CreateDesign.SeamAccent = EnumCycle.Next(App.CreateDesign.SeamAccent); Refresh(); });
            FrUiFactory.AddButton(col, "Palette -> next", t, () => { _ = CyclePaletteAsync(); });
            FrUiFactory.AddButton(col, "Choose material", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.MaterialSelection);
            });
            FrUiFactory.AddButton(col, "Model preview", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ModelPreview);
            });
            FrUiFactory.AddButton(col, "Save draft (mock)", t, () => { _ = SaveDraftAsync(); });
            FrUiFactory.AddButton(col, "Export PNG (mock)", t, () => { _ = ExportAsync(); });
            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload) => _ = BootstrapDefaultsAsync();

        async Task BootstrapDefaultsAsync()
        {
            if (string.IsNullOrEmpty(App.CreateDesign.TemplateId))
            {
                var tpl = await App.Templates.GetTemplatesAsync(App.CreateDesign.Category).ConfigureAwait(true);
                if (tpl.Count > 0)
                    App.CreateDesign.TemplateId = tpl[0].Id;
            }

            if (string.IsNullOrEmpty(App.CreateDesign.ColorPaletteId))
            {
                var pal = await App.Palettes.GetPalettesAsync().ConfigureAwait(true);
                if (pal.Count > 0)
                    App.CreateDesign.ColorPaletteId = pal[0].Id;
            }

            if (App.IsApiBackend)
            {
                var mats = await App.Materials.GetMaterialsAsync().ConfigureAwait(true);
                if (mats.Count > 0 &&
                    (string.IsNullOrEmpty(App.CreateDesign.MaterialId) ||
                     !System.Guid.TryParse(App.CreateDesign.MaterialId, out _)))
                    App.CreateDesign.MaterialId = mats[0].Id;
            }
            else if (string.IsNullOrEmpty(App.CreateDesign.MaterialId))
            {
                App.CreateDesign.MaterialId = "mat_satin";
            }

            Refresh();
        }

        void Refresh()
        {
            var s = App.CreateDesign;
            _summary.text =
                $"Category: {s.Category}\n" +
                $"Template: {s.TemplateId}\n" +
                $"Neckline: {s.Neckline}  Sleeve: {s.Sleeve}\n" +
                $"Length: {s.Length}  Fit: {s.Fit}  Waist: {s.Waist}\n" +
                $"V2: vol {s.SilhouetteVolume}  drape {s.DrapeExpression}  layer {s.LayeringDepth}  seam {s.SeamAccent}\n" +
                $"Sketch ref: {s.SketchReference}\n" +
                $"Palette: {s.ColorPaletteId}\n" +
                $"Material: {s.MaterialId}";
        }

        async Task CycleTemplateAsync()
        {
            var list = await App.Templates.GetTemplatesAsync(App.CreateDesign.Category).ConfigureAwait(true);
            if (list.Count == 0)
                return;
            var idx = string.IsNullOrEmpty(App.CreateDesign.TemplateId)
                ? 0
                : System.Math.Max(0, list.ToList().FindIndex(t => t.Id == App.CreateDesign.TemplateId));
            var next = list[(idx + 1) % list.Count];
            App.CreateDesign.TemplateId = next.Id;
            Refresh();
        }

        async Task CyclePaletteAsync()
        {
            var list = await App.Palettes.GetPalettesAsync().ConfigureAwait(true);
            if (list.Count == 0)
                return;
            var idx = string.IsNullOrEmpty(App.CreateDesign.ColorPaletteId)
                ? 0
                : System.Math.Max(0, list.ToList().FindIndex(p => p.Id == App.CreateDesign.ColorPaletteId));
            var next = list[(idx + 1) % list.Count];
            App.CreateDesign.ColorPaletteId = next.Id;
            Refresh();
        }

        async Task SaveDraftAsync()
        {
            var uid = App.Auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
                return;
            var d = App.CreateDesign.ToDraft(uid, "Studio draft");
            try
            {
                await App.DesignSave.SaveDraftAsync(d).ConfigureAwait(true);
            }
            catch (System.Exception ex)
            {
                UnityEngine.Debug.LogWarning($"Save draft failed: {ex.Message}");
            }
        }

        async Task ExportAsync()
        {
            var uid = App.Auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
                return;
            var d = App.CreateDesign.ToDraft(uid, "Export");
            if (App.Auth.HasBackendSession)
            {
                try
                {
                    d = await App.DesignSave.SaveDraftAsync(d).ConfigureAwait(true);
                }
                catch (System.Exception ex)
                {
                    UnityEngine.Debug.LogWarning($"Save before export failed: {ex.Message}");
                }
            }

            var req = new ExportRequest { DesignId = d.Id, FileName = "fashionrise_look" };
            await App.Export.ExportPngAsync(req).ConfigureAwait(true);
        }
    }
}
