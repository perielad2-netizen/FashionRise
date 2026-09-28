using System.Collections.Generic;
using MathGame.Player;
using MathGame.UI;
using UnityEngine;

namespace MathGame.Interaction
{
    public class PlayerInteractor : MonoBehaviour
    {
        [SerializeField, Min(0.05f)] float detectionRadius = 0.45f;
        [SerializeField] InteractionPrompt prompt;
        [SerializeField, Min(0.2f)] float feedbackDuration = 2.75f;

        readonly List<IInteractable> _candidates = new List<IInteractable>(4);
        IInteractable _current;
        string _feedback;
        float _feedbackUntil;
        PlayerController _player;

        void Awake()
        {
            _player = GetComponent<PlayerController>();
        }

        void Update()
        {
            if (_player != null && _player.MovementLocked)
            {
                prompt?.Hide();
                return;
            }

            _current = FindClosest();
            bool showingFeedback = Time.time < _feedbackUntil && !string.IsNullOrEmpty(_feedback);

            if (showingFeedback)
                prompt?.Show(_feedback);
            else if (_current != null)
                prompt?.Show(string.IsNullOrEmpty(_current.Prompt) ? "Press E to interact" : _current.Prompt);
            else
                prompt?.Hide();

            if (_current == null || showingFeedback || !Input.GetKeyDown(KeyCode.E))
                return;

            _feedback = _current.Interact();
            if (!string.IsNullOrEmpty(_feedback))
                _feedbackUntil = Time.time + feedbackDuration;
        }

        IInteractable FindClosest()
        {
            _candidates.Clear();
            Collider2D[] hits = Physics2D.OverlapCircleAll(transform.position, detectionRadius);
            Vector2 origin = transform.position;
            IInteractable closest = null;
            float bestDistance = float.MaxValue;

            for (int i = 0; i < hits.Length; i++)
            {
                if (hits[i].transform == transform || hits[i].transform.IsChildOf(transform))
                    continue;

                IInteractable interactable = hits[i].GetComponentInParent<IInteractable>();
                if (interactable == null || _candidates.Contains(interactable))
                    continue;

                _candidates.Add(interactable);
                Vector2 point = ((Component)interactable).transform.position;
                float distance = Vector2.Distance(origin, point);
                if (distance > interactable.InteractionRange || distance >= bestDistance)
                    continue;

                bestDistance = distance;
                closest = interactable;
            }

            return closest;
        }

        void OnDrawGizmosSelected()
        {
            Gizmos.color = new Color(1f, 0.9f, 0.2f, 0.8f);
            Gizmos.DrawWireSphere(transform.position, detectionRadius);
        }
    }
}
