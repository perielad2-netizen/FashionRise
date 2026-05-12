using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Infrastructure.Api;
using FashionRise.Services;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockDesignHandoffService : IDesignHandoffService
    {
        readonly IDesignSaveService _designs;

        public MockDesignHandoffService(IDesignSaveService designs) => _designs = designs;

        public async Task<string?> GetHandoffManifestJsonAsync(string designId,
            string exportKind = "manifest_v1",
            CancellationToken cancellationToken = default)
        {
            var d = await _designs.GetDesignByIdAsync(designId, cancellationToken).ConfigureAwait(true);
            if (d == null)
                return null;
            var title = d.Metadata?.Title ?? "Draft";
            var kind = string.IsNullOrWhiteSpace(exportKind) ? "manifest_v1" : exportKind.Trim();
            var exportKindName = kind switch
            {
                "spec_sheet_v1" => "fashionrise.handoff.spec_sheet_v1",
                "spec_sheet_pdf" => "fashionrise.handoff.spec_sheet_pdf_v1",
                _ => "fashionrise.handoff.manifest_v1"
            };
            var o = new JObject
            {
                ["schema_version"] = "1.0",
                ["export_kind"] = exportKindName,
                ["generated_at"] = DateTime.UtcNow.ToString("o"),
                ["design"] = new JObject
                {
                    ["id"] = d.Id,
                    ["title"] = title,
                    ["description"] = null,
                    ["garment_category"] = d.Category.ToString(),
                    ["status"] = d.Status,
                    ["visibility"] = "private",
                    ["template_id"] = string.IsNullOrEmpty(d.TemplateId) ? null : d.TemplateId,
                    ["material_id"] = string.IsNullOrEmpty(d.MaterialId) ? null : d.MaterialId,
                    ["color_palette_id"] = string.IsNullOrEmpty(d.ColorPaletteId) ? null : d.ColorPaletteId,
                },
                ["linked_catalog"] = new JObject(),
                ["design_data"] = JObject.FromObject(ApiDomainMapper.BuildDesignDataDictionary(d)),
                ["metadata"] = new JObject(),
                ["revision_summary"] = new JObject
                {
                    ["count"] = 0,
                    ["latest_revision_number"] = null,
                    ["recent"] = new JArray()
                },
                ["export_hints"] = new JObject
                {
                    ["intended_consumers"] = new JArray("maker", "atelier", "classroom"),
                    ["next_exports"] = new JArray("spec_sheet_pdf", "cut_plan_pdf"),
                    ["notes"] = "This manifest is JSON-first; print-ready package export types are planned."
                },
                ["export"] = kind == "spec_sheet_pdf"
                    ? new JObject
                    {
                        ["id"] = Guid.NewGuid().ToString("N"),
                        ["design_id"] = d.Id,
                        ["export_type"] = "spec_sheet_pdf",
                        ["file_url"] = $"https://mock.fashionrise/export/spec_sheet_{d.Id}.pdf",
                        ["metadata"] = new JObject
                        {
                            ["source"] = "mock",
                            ["export_kind"] = "spec_sheet_pdf"
                        },
                        ["created_at"] = DateTime.UtcNow.ToString("o")
                    }
                    : null,
                ["style_recipe"] = kind == "spec_sheet_v1" || kind == "spec_sheet_pdf"
                    ? new JObject
                    {
                        ["template"] = string.IsNullOrEmpty(d.TemplateId) ? null : d.TemplateId,
                        ["material"] = string.IsNullOrEmpty(d.MaterialId) ? null : d.MaterialId,
                        ["palette"] = string.IsNullOrEmpty(d.ColorPaletteId) ? null : d.ColorPaletteId,
                        ["silhouette_volume"] = d.SilhouetteVolume.ToString(),
                        ["drape_expression"] = d.DrapeExpression.ToString(),
                        ["layering_depth"] = d.LayeringDepth.ToString(),
                        ["seam_accent"] = d.SeamAccent.ToString(),
                    }
                    : null,
                ["measurements_placeholder"] = new JObject
                {
                    ["note"] = "Reserved for bust, waist, hip, inseam, etc. — add when fit capture ships.",
                },
            };
            return o.ToString(Formatting.Indented);
        }
    }
}
