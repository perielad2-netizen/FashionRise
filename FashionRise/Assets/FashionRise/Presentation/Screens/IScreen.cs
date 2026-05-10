using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;

namespace FashionRise.Presentation.Screens
{
    public interface IScreen
    {
        ScreenId Id { get; }

        Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default);

        Task HideAsync(CancellationToken cancellationToken = default);
    }
}
