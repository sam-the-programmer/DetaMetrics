const ctx{{ i }} = document.getElementById('c{{ i }}');

new Chart(ctx{{ i }}, {
  type: "line",
  data: {
    labels: {{ labels }},
    datasets: {{ datasets }},
  }
});
