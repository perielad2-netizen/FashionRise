namespace MathGame.Interaction
{
    public interface IInteractable
    {
        string Prompt { get; }
        float InteractionRange { get; }
        string Interact();
    }
}
