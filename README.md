# Parkourse

CS 175 project exploring whether a small reinforcement learning agent can learn to time Minecraft parkour jumps.

A course supplies the next platform. The controller holds one of seven actions for two ticks and reports raw player state. The same Minecraft Java world can run headless or be watched in a graphical client.

## Team TODOs

- Set up the observations for learning: distance and height to the next platform, forward and vertical speed, and ground contact.
- Define rewards, episode endings, and the Q-learning policy.
- Evaluate on held-out jumps and courses.
