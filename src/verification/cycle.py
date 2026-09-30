"""Independent reverse matching; inverse(H) alone is not cycle evidence."""
import numpy as np
from src.matching.baseline import bounded_matches, project_points
from src.verification.robust import verify
from src.evaluation.metrics import summarize_errors


def reverse_cycle(a, b, mask_a, mask_b, forward, points, config):
    prior = np.linalg.inv(np.asarray(config['source_to_target_prior'], float))
    radius = config.get('reverse_search_radius_source_working_px', config['search_radius_target_working_px'])
    xb, xa, _, _ = bounded_matches(b, a, mask_b, mask_a, prior, radius,
        config['ratio_filter'], config['matcher'], config['max_features'])
    back = verify(xb, xa, config.get('reverse_robust', config['robust']))
    if back['reason'] or back['matrix'] is None or len(points) == 0:
        return {'status':'UNAVAILABLE', 'method':'independent reverse feature detection and robust fit',
                'reverse_candidates':len(xb), 'reason':back['reason'], 'rmse':None}
    returned = project_points(project_points(points, forward), back['matrix'])
    stats = summarize_errors(np.linalg.norm(returned-points, axis=1),
        config.get('source_working_grid', 'source working pixel grid'), 'forward inliers returned through independently fitted reverse model')
    stats.update(status='MEASURED', method='independent reverse feature detection and robust fit',
                 reverse_candidates=len(xb), reverse_inliers=int(back['inliers'].sum()), reverse_matrix=back['matrix'].tolist())
    return stats
