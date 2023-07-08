frappe.ui.form.on('Interview Feedback', {
	interview_round: function(frm) {
		frappe.call({
			method: 'one_fm.hiring.utils.get_interview_question_set',
			args: {
				interview_round: frm.doc.interview_round
			},
			callback: function(r) {
				frm.set_value('interview_question_assessment', r.message);
			}
		});
		
	},
	onload: function(frm){
		console.log("hey")
		frm.set_query('interviewer', () => {
			return {
				filters: {
					"enabled": True
				}
			}
		})
	}
});
