from backend.app.services.turkish_ner import detect_named_entities


text = (
    "Ayşe Yılmaz İstanbul'daki "
    "ABC Teknoloji şirketinde çalışıyor."
)


findings = detect_named_entities(text)

for finding in findings:
    print(finding)