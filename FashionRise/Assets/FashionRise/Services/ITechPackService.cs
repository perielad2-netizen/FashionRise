using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;

namespace FashionRise.Services
{
    public interface ITechPackService
    {
        Task<TechPackResult> GenerateAsync(TechPackRequest request, CancellationToken cancellationToken = default);
    }
}
