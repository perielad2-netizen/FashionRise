using System;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Application;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    /// <summary>
    /// Offline export simulation (no file IO). [V2_READY] swap for UnityPngExportService.
    /// </summary>
    public sealed class MockExportService : IExportService
    {
        public Task<ExportResult> ExportPngAsync(ExportRequest request,
            CancellationToken cancellationToken = default)
        {
            var package = new ExportPackage
            {
                ExportId = Guid.NewGuid().ToString("N"),
                DesignId = request.DesignId,
                LocalPngPath = $"(mock)/exports/{request.FileName}.png",
                CreatedAtUtc = DateTime.UtcNow,
                Width = request.Width,
                Height = request.Height
            };

            return Task.FromResult(new ExportResult
            {
                Success = true,
                Message = "Mock export recorded.",
                Package = package
            });
        }
    }
}
