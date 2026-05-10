using System.Threading;
using System.Threading.Tasks;
using FashionRise.Presentation.Screens;

namespace FashionRise.Presentation.Navigation
{
    /// <summary>
    /// [V2_READY] Cross-fade / slide transitions between screen roots.
    /// </summary>
    public sealed class ScreenTransitionService
    {
        public Task PlayInstantAsync(ScreenBase from, ScreenBase to,
            CancellationToken cancellationToken = default)
        {
            return Task.CompletedTask;
        }
    }
}
