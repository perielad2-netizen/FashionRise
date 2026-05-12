using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;
using UnityEngine;

namespace FashionRise.Infrastructure.Api
{
    public sealed class DesignApiService : IDesignSaveService
    {
        readonly ApiClient _client;

        public DesignApiService(ApiClient client) => _client = client;

        public async Task<GarmentDesign> SaveDraftAsync(GarmentDesign design,
            CancellationToken cancellationToken = default)
        {
            GarmentDesign result;
            if (ApiDomainMapper.LooksLikeClientGeneratedDesignId(design.Id))
            {
                var created = await _client
                    .PostJsonAsync<DesignReadDto>("/designs", ApiDomainMapper.ToDesignCreateBody(design),
                        cancellationToken, useBearer: true)
                    .ConfigureAwait(true);
                result = ApiDomainMapper.ToGarmentDesign(created);
            }
            else if (!Guid.TryParse(design.Id, out _))
            {
                var created = await _client
                    .PostJsonAsync<DesignReadDto>("/designs", ApiDomainMapper.ToDesignCreateBody(design),
                        cancellationToken, useBearer: true)
                    .ConfigureAwait(true);
                result = ApiDomainMapper.ToGarmentDesign(created);
            }
            else
            {
                var gid = Guid.Parse(design.Id);
                var updated = await _client
                    .PutJsonAsync<DesignReadDto>($"/designs/{gid}", ApiDomainMapper.ToDesignUpdateBody(design),
                        cancellationToken, useBearer: true)
                    .ConfigureAwait(true);
                result = ApiDomainMapper.ToGarmentDesign(updated);
            }

            await TryAppendRevisionAfterSaveAsync(result, cancellationToken).ConfigureAwait(true);
            return result;
        }

        async Task TryAppendRevisionAfterSaveAsync(GarmentDesign result, CancellationToken ct)
        {
            try
            {
                await AppendRevisionSnapshotAsync(result.Id, result, notes: null, ct).ConfigureAwait(true);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"FashionRise: revision snapshot skipped after save ({ex.Message})");
            }
        }

        public async Task<int> AppendRevisionSnapshotAsync(string designId, GarmentDesign design, string? notes = null,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(designId, out var gid))
                throw new ArgumentException("designId must be a server design UUID.", nameof(designId));
            var body = new
            {
                design_data = ApiDomainMapper.BuildDesignDataDictionary(design),
                notes
            };
            var dto = await _client
                .PostJsonAsync<DesignRevisionReadDto>($"/designs/{gid}/revisions", body, cancellationToken, true)
                .ConfigureAwait(true);
            return dto.RevisionNumber;
        }

        public async Task<IReadOnlyList<DesignRevisionSnapshot>> ListRevisionSnapshotsAsync(string designId,
            int limit = 30, int offset = 0, CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(designId, out var gid))
                return Array.Empty<DesignRevisionSnapshot>();
            var list = await _client
                .GetJsonAsync<List<DesignRevisionReadDto>>(
                    $"/designs/{gid}/revisions?limit={limit}&offset={offset}",
                    cancellationToken, useBearer: true)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToDesignRevisionSnapshot).ToList();
        }

        static GarmentDesign CloneDesign(GarmentDesign d) =>
            new()
            {
                Id = d.Id,
                OwnerUserId = d.OwnerUserId,
                Metadata = new DesignMetadata
                {
                    Title = d.Metadata.Title,
                    CreatedAtUtc = d.Metadata.CreatedAtUtc
                },
                Category = d.Category,
                TemplateId = d.TemplateId,
                Neckline = d.Neckline,
                Sleeve = d.Sleeve,
                Length = d.Length,
                Fit = d.Fit,
                Waist = d.Waist,
                ColorPaletteId = d.ColorPaletteId,
                MaterialId = d.MaterialId,
                Status = d.Status,
                ExtensionData = d.ExtensionData,
                SilhouetteVolume = d.SilhouetteVolume,
                DrapeExpression = d.DrapeExpression,
                LayeringDepth = d.LayeringDepth,
                SeamAccent = d.SeamAccent,
                TrimNotes = d.TrimNotes,
                AccentNotes = d.AccentNotes,
                SketchReference = d.SketchReference
            };

        public async Task<GarmentDesign?> ApplyRevisionToDesignAsync(string designId, int revisionNumber, GarmentDesign baseDesign,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(designId, out var gid))
                return null;
            if (revisionNumber <= 0)
                return null;

            try
            {
                var dto = await _client
                    .GetJsonAsync<DesignRevisionReadDto>($"/designs/{gid}/revisions/{revisionNumber}", cancellationToken,
                        useBearer: true)
                    .ConfigureAwait(true);
                var merged = CloneDesign(baseDesign);
                ApiDomainMapper.ApplyDesignDataToDesign(dto.DesignData, merged);
                return merged;
            }
            catch (ApiException)
            {
                return null;
            }
        }

        public async Task<IReadOnlyList<GarmentDesign>> ListMyDesignsAsync(
            CancellationToken cancellationToken = default)
        {
            var list = await _client
                .GetJsonAsync<List<DesignReadDto>>("/designs/my", cancellationToken, useBearer: true)
                .ConfigureAwait(true);
            return list.Select(ApiDomainMapper.ToGarmentDesign).ToList();
        }

        public async Task<GarmentDesign?> GetDesignByIdAsync(string designId,
            CancellationToken cancellationToken = default)
        {
            if (!Guid.TryParse(designId, out var gid))
                return null;
            try
            {
                var d = await _client.GetJsonAsync<DesignReadDto>($"/designs/{gid}", cancellationToken, true)
                    .ConfigureAwait(true);
                return ApiDomainMapper.ToGarmentDesign(d);
            }
            catch (ApiException)
            {
                return null;
            }
        }
    }
}
