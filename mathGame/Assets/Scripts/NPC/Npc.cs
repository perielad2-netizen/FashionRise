using MathGame.Interaction;
using MathGame.Quests;
using UnityEngine;

namespace MathGame.NPC
{
    [RequireComponent(typeof(CircleCollider2D))]
    public class Npc : MonoBehaviour, IInteractable
    {
        [SerializeField] string displayName = "Raccoon";
        [SerializeField, Min(0.2f)] float interactionRadius = 1.25f;
        [SerializeField] string responseLine = "Raccoon: Hi. I'm the raccoon. More to say later.";
        [SerializeField] QuestGiver questGiver;

        CircleCollider2D _range;

        public string DisplayName => displayName;
        public string Prompt => "Press E to interact";
        public float InteractionRange => interactionRadius;

        void Awake()
        {
            ApplyRadius();
        }

        void OnValidate()
        {
            ApplyRadius();
        }

        public string Interact()
        {
            if (questGiver != null)
                return questGiver.HandleInteract();

            return responseLine;
        }

        void ApplyRadius()
        {
            if (_range == null)
                _range = GetComponent<CircleCollider2D>();

            if (_range == null)
                return;

            _range.isTrigger = true;
            _range.radius = interactionRadius;
        }

        void OnDrawGizmosSelected()
        {
            Gizmos.color = new Color(0.4f, 0.8f, 1f, 0.9f);
            Gizmos.DrawWireSphere(transform.position, interactionRadius);
        }
    }
}
