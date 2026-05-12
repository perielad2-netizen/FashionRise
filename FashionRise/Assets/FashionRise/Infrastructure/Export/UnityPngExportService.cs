using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Application;
using FashionRise.Domain;
using FashionRise.Services;
using UnityEngine;

namespace FashionRise.Infrastructure.Export
{
    /// <summary>
    /// Placeholder PNG path using full-frame capture. [V2_READY] render-target export from preview camera.
    /// [API_READY] Upload via POST /uploads then POST /exports.
    /// </summary>
    public sealed class UnityPngExportService : IExportService
    {
        public Task<ExportResult> ExportPngAsync(ExportRequest request,
            CancellationToken cancellationToken = default)
        {
            var safeName = string.IsNullOrWhiteSpace(request.FileName)
                ? "fashionrise_export"
                : Path.GetFileNameWithoutExtension(request.FileName);
            // Editor / standalone: bare filename is saved under the project folder, not persistentDataPath.
            // Use a full path so PublishingExportService can read the same file for POST /uploads/image.
            var path = Path.Combine(UnityEngine.Application.persistentDataPath, safeName + ".png");
            ScreenCapture.CaptureScreenshot(path);

            var package = new ExportPackage
            {
                ExportId = Guid.NewGuid().ToString("N"),
                DesignId = request.DesignId,
                LocalPngPath = path,
                CreatedAtUtc = DateTime.UtcNow,
                Width = request.Width,
                Height = request.Height
            };

            return Task.FromResult(new ExportResult
            {
                Success = true,
                Message = "Screenshot captured to persistent data path (placeholder).",
                Package = package
            });
        }
    }
}
