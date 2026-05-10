using System.Threading;
using System.Threading.Tasks;
using FashionRise.Application;

namespace FashionRise.Services
{
    public interface IExportService
    {
        Task<ExportResult> ExportPngAsync(ExportRequest request,
            CancellationToken cancellationToken = default);
    }
}
